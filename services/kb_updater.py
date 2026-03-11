"""
services/kb_updater.py
======================
Knowledge Base updater: extracts text from uploaded PDF, TXT, or DOCX files
and updates core/knowledge_base.py after admin confirmation.

Flow:
  1. Admin DMs bot a document
  2. Bot extracts text (tries direct extraction first, then OCR for image-based PDFs)
  3. Admin reviews preview + confirms
  4. KB updated live — no restart needed
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc"}

KB_FILE_PATH = Path(__file__).resolve().parent.parent / "core" / "knowledge_base.py"

# Temp store for pending KB content per admin: {user_id: extracted_text}
pending_kb_updates: dict[int, str] = {}
MIN_DIRECT_PDF_TEXT_CHARS = 100


# ─────────────────────────────────────────────
# TEXT EXTRACTION
# ─────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF.
    Strategy:
      1. Try direct text extraction via PyMuPDF (fast, works for text-based PDFs)
      2. If result is too short, fall back to OCR via pytesseract
    """
    import fitz  # pymupdf

    doc = fitz.open(file_path)
    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())
    doc.close()

    direct_text = "\n".join(pages_text).strip()

    # If we got enough real text, use it
    if len(direct_text) >= MIN_DIRECT_PDF_TEXT_CHARS:
        logger.info(f"[KB] PDF direct extraction: {len(direct_text)} chars")
        return direct_text

    # Otherwise try OCR
    logger.info("[KB] PDF direct extraction too short, attempting OCR...")
    return _extract_pdf_ocr(file_path)


def _extract_pdf_ocr(file_path: str) -> str:
    """OCR fallback for image-based PDFs using pytesseract on rendered PDF pages."""
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image

        if not shutil.which("tesseract"):
            raise ValueError(
                "Tesseract OCR binary is not installed on this server.\n\n"
                "Install it (apt/yum/choco) and try again, or upload a TXT file."
            )

        doc = fitz.open(file_path)
        pages_text = []
        for i, page in enumerate(doc):
            # Render at ~200 DPI for better OCR accuracy.
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang="eng")
            if text.strip():
                pages_text.append(text.strip())
            logger.info(f"[KB] OCR page {i+1}/{len(doc)}: {len(text)} chars")
        doc.close()

        result = "\n\n".join(pages_text).strip()
        logger.info(f"[KB] OCR total: {len(result)} chars across {len(pages_text)} non-empty pages")
        return result

    except ImportError as e:
        raise ValueError(
            "This PDF contains image-based text and requires OCR tools.\n\n"
            f"Missing dependency: {e}. Install `pytesseract` and `Pillow`, then retry.\n"
            "If unavailable, upload the content as a *.txt file* instead."
        )
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise ValueError(
            f"OCR extraction failed: {e}\n\n"
            "Please try uploading the content as a *.txt file* instead."
        )


def extract_text_from_docx(file_path: str) -> str:
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        raise ValueError(f"Could not read DOCX: {e}")


def extract_text_from_txt(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"TXT extraction error: {e}")
        raise ValueError(f"Could not read TXT: {e}")


def extract_text(file_path: str, file_name: str) -> str:
    """Detect file type by extension and extract text."""
    ext = Path(file_name).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in {".docx", ".doc"}:
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: PDF, TXT, DOCX")


# ─────────────────────────────────────────────
# KB FILE UPDATE
# ─────────────────────────────────────────────

def write_kb_to_file(content: str) -> None:
    """Overwrite core/knowledge_base.py with new KB content."""
    safe_content = content.replace('"""', "'''")
    kb_file_content = f'''"""
core/knowledge_base.py
======================
Kickchain project knowledge base used by the /ask command.
Last updated via /uploadkb admin command.
Update by uploading a new document via DM to the bot.
"""

KICKCHAIN_KB = """{safe_content}
"""
'''
    KB_FILE_PATH.write_text(kb_file_content, encoding="utf-8")
    logger.info("[KB] Knowledge base file updated successfully.")


def reload_kb_in_memory(new_content: str) -> None:
    """Hot-reload the KB string in memory without restarting the bot."""
    import core.knowledge_base as kb_module
    kb_module.KICKCHAIN_KB = new_content
    import services.answering as answering_module
    answering_module.KICKCHAIN_KB = new_content
    logger.info("[KB] Knowledge base reloaded in memory.")


def apply_kb_update(user_id: int) -> bool:
    """Apply the pending KB update. Returns True on success."""
    content = pending_kb_updates.pop(user_id, None)
    if not content:
        return False
    write_kb_to_file(content)
    reload_kb_in_memory(content)
    return True


def discard_kb_update(user_id: int) -> None:
    """Discard a pending KB update."""
    pending_kb_updates.pop(user_id, None)
