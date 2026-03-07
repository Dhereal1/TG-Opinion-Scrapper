"""
memory/chat_memory.py
=====================
Persistent chat memory JSONL helpers and lexical retrieval for /ask grounding.
"""

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from utils.helpers import normalize_text, tokenize_text

BASE_DIR = Path(__file__).resolve().parent.parent
CHAT_MEMORY_PATH = BASE_DIR / "memory" / "chat_memory.jsonl"

MEMORY_MIN_LEN = 8
MEMORY_TOP_K = 5
MEMORY_CANDIDATE_LIMIT = 2500


def log_chat_memory(
    user: str,
    user_id: int,
    text: str,
    msg_url: str = "",
    source: str = "live",
    original_ts: str = "",
):
    """Append a chat message to persistent memory for retrieval."""
    clean = normalize_text(text)
    if len(clean) < MEMORY_MIN_LEN:
        return

    CHAT_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "user_id": user_id,
        "text": clean,
        "msg_url": msg_url,
        "source": source,
    }
    if original_ts:
        entry["original_ts"] = original_ts

    with open(CHAT_MEMORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")



def load_recent_memory(limit: int = MEMORY_CANDIDATE_LIMIT) -> list[dict]:
    """Load recent memory entries from JSONL."""
    if limit <= 0:
        return []

    recent_lines: deque[str] = deque(maxlen=limit)
    try:
        with open(CHAT_MEMORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                recent_lines.append(line)
    except FileNotFoundError:
        return []

    entries = []
    for line in recent_lines:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries



def retrieve_memory_snippets(question: str, top_k: int = MEMORY_TOP_K) -> list[dict]:
    """Simple lexical retrieval from memory JSONL for grounded answers."""
    q_tokens = tokenize_text(question)
    if not q_tokens:
        return []

    entries = load_recent_memory(MEMORY_CANDIDATE_LIMIT)
    if not entries:
        return []

    min_overlap = 1
    scored: list[tuple[int, int, dict]] = []

    # Newer entries get a tiny tiebreak via recency_rank (smaller is newer).
    for recency_rank, entry in enumerate(reversed(entries)):
        text = normalize_text(entry.get("text", ""))
        if len(text) < MEMORY_MIN_LEN:
            continue
        overlap = len(q_tokens & tokenize_text(text))
        if overlap < min_overlap:
            continue
        score = overlap * 3
        low_q = question.lower()
        low_t = text.lower()
        if low_q in low_t or low_t in low_q:
            score += 2
        scored.append((score, -recency_rank, entry))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item[2] for item in scored[:top_k]]



def format_memory_context(snippets: list[dict]) -> str:
    if not snippets:
        return "No matching community memory snippets found."

    rows = []
    for idx, s in enumerate(snippets, start=1):
        ts = s.get("original_ts") or s.get("ts", "")
        user = s.get("user", "unknown")
        text = normalize_text(s.get("text", ""))[:300]
        rows.append(f"{idx}. [{ts}] {user}: {text}")
    return "\n".join(rows)



def load_existing_keys(file_path: Path) -> set[str]:
    """Load stable dedupe keys from JSONL files."""
    keys = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    user_id = int(e.get("user_id", 0))
                    text = str(e.get("text", ""))
                    keys.add(f"{user_id}::{normalize_text(text).lower()}")
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return keys



def load_existing_memory_keys() -> set[str]:
    """Used to avoid duplicate memory entries across multiple scans."""
    return load_existing_keys(CHAT_MEMORY_PATH)
