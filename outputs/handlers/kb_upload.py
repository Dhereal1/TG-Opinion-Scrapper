"""
handlers/kb_upload.py
=====================
Handles admin document uploads for KB updates via private DM.

Commands & flow:
  1. Admin DMs bot a PDF/TXT/DOCX file
  2. Bot extracts text, shows preview + Confirm/Cancel buttons
  3. Admin taps Confirm → KB updated live (no restart needed)
  4. Admin taps Cancel → nothing changes

Also handles: /uploadkb command to show usage instructions.
"""

import logging
import tempfile
import os

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.helpers import is_admin
from services.kb_updater import (
    extract_text,
    pending_kb_updates,
    apply_kb_update,
    discard_kb_update,
    SUPPORTED_EXTENSIONS,
)

logger = logging.getLogger(__name__)

CB_KB_CONFIRM = "kb_confirm"
CB_KB_CANCEL  = "kb_cancel"

KB_CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Confirm — Update KB", callback_data=CB_KB_CONFIRM),
        InlineKeyboardButton("❌ Cancel",              callback_data=CB_KB_CANCEL),
    ]
])


# ─────────────────────────────────────────────
# /uploadkb COMMAND
# ─────────────────────────────────────────────

async def cmd_uploadkb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: show instructions for uploading a KB document."""
    msg  = update.message
    user = update.effective_user
    if not msg or not user:
        return
    if not is_admin(user.id):
        await msg.reply_text("⛔ Admin only command.")
        return

    await msg.reply_text(
        "📄 *Knowledge Base Upload*\n\n"
        "Send me a document in this private chat to update the bot's knowledge base.\n\n"
        "Supported formats:\n"
        "• PDF (.pdf)\n"
        "• Word document (.docx)\n"
        "• Plain text (.txt)\n\n"
        "After uploading, I'll show you a preview of the extracted content "
        "and ask you to confirm before applying the update.\n\n"
        "_The update takes effect instantly — no restart needed._",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
# DOCUMENT UPLOAD HANDLER
# ─────────────────────────────────────────────

async def on_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document uploads in private chat from admins."""
    msg  = update.message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not user or not chat:
        return
    if chat.type != "private":
        return
    if not is_admin(user.id):
        return

    doc = msg.document
    if not doc:
        return

    file_name = doc.file_name or "upload"
    ext       = os.path.splitext(file_name)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        await msg.reply_text(
            f"❌ Unsupported file type: `{ext}`\n\n"
            "Please upload a *PDF*, *DOCX*, or *TXT* file.",
            parse_mode="Markdown",
        )
        return

    await msg.reply_text(f"📥 Received `{file_name}` — extracting content...", parse_mode="Markdown")

    # Download the file
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
        await tg_file.download_to_drive(tmp_path)
    except Exception as e:
        logger.error(f"File download error: {e}")
        await msg.reply_text(f"❌ Failed to download file: {e}")
        return

    # Extract text
    try:
        extracted = extract_text(tmp_path, file_name)
    except ValueError as e:
        await msg.reply_text(f"❌ {e}")
        return
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        await msg.reply_text(f"❌ Unexpected error during extraction: {e}")
        return
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not extracted or len(extracted.strip()) < 50:
        await msg.reply_text(
            "⚠️ Extracted content is too short or empty. "
            "Please check the file and try again."
        )
        return

    # Store pending update
    pending_kb_updates[user.id] = extracted

    # Show preview to admin
    preview   = extracted[:800].strip()
    char_count = len(extracted)
    word_count = len(extracted.split())

    await msg.reply_text(
        f"📋 *Extracted Content Preview*\n\n"
        f"📊 {char_count:,} characters | {word_count:,} words\n\n"
        f"```\n{preview}\n```\n"
        f"{'...(truncated)' if char_count > 800 else ''}\n\n"
        "⚠️ *This will replace the current knowledge base.*\n"
        "Confirm to apply, or cancel to discard.",
        parse_mode="Markdown",
        reply_markup=KB_CONFIRM_KEYBOARD,
    )


# ─────────────────────────────────────────────
# CONFIRM / CANCEL CALLBACKS
# ─────────────────────────────────────────────

async def on_kb_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Confirm/Cancel inline button for KB update."""
    query = update.callback_query
    user  = update.effective_user
    if not query or not user:
        return
    await query.answer()

    if not is_admin(user.id):
        await query.edit_message_text("⛔ Admin only.")
        return

    if query.data == CB_KB_CONFIRM:
        success = apply_kb_update(user.id)
        if success:
            await query.edit_message_text(
                "✅ *Knowledge base updated successfully!*\n\n"
                "The bot will now use the new content for all `/ask` responses. "
                "No restart required.",
                parse_mode="Markdown",
            )
            logger.info("[KB] Admin %s confirmed KB update.", user.id)
        else:
            await query.edit_message_text(
                "⚠️ No pending update found. Please upload a document again."
            )

    elif query.data == CB_KB_CANCEL:
        discard_kb_update(user.id)
        await query.edit_message_text(
            "❌ *KB update cancelled.* No changes were made.",
            parse_mode="Markdown",
        )
        logger.info("[KB] Admin %s cancelled KB update.", user.id)
