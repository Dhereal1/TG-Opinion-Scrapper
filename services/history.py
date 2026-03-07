"""
services/history.py
===================
Backfill logic for Telegram export history (/scanhistory).
"""

import json
import os
import re
from pathlib import Path

from core.config import GROUP_ID
from memory.chat_memory import MEMORY_MIN_LEN, load_existing_memory_keys, log_chat_memory
from services.opinions import load_existing_opinion_keys, log_opinion
from services.signals import detect_signal
from utils.helpers import (
    build_message_url,
    extract_export_text,
    make_dedupe_key,
    parse_export_user_id,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def resolve_export_json_path(export_path: str) -> Path:
    """
    Accept either a JSON export path directly, or messages.html path and
    auto-resolve sibling result.json (Telegram Desktop export layout).
    """
    win_path_match = re.match(r"^([A-Za-z]):[\\/](.*)$", export_path)
    if win_path_match and os.name != "nt":
        drive = win_path_match.group(1).lower()
        rest = win_path_match.group(2).replace("\\", "/")
        p = Path(f"/mnt/{drive}/{rest}")
    else:
        p = Path(export_path)

    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()

    if p.suffix.lower() == ".html":
        sibling_json = p.with_name("result.json")
        if sibling_json.exists():
            return sibling_json
        raise FileNotFoundError(f"Could not find sibling result.json for {p}")

    if not p.exists():
        raise FileNotFoundError(f"Export file not found: {p}")
    return p



def scan_history_export(export_path: str, limit: int = 0) -> dict:
    """
    Scan Telegram exported history and backfill memory + detected opinions.
    """
    resolved_path = resolve_export_json_path(export_path)
    with open(resolved_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    if limit > 0:
        messages = messages[-limit:]

    existing_opinions = load_existing_opinion_keys()
    existing_memory = load_existing_memory_keys()
    scanned = 0
    opinions_matched = 0
    opinions_inserted = 0
    memory_inserted = 0

    for m in messages:
        if m.get("type") != "message":
            continue

        text = extract_export_text(m.get("text", "")).strip()
        if not text:
            continue

        scanned += 1
        user_id = parse_export_user_id(m.get("from_id"))
        user = m.get("from", "unknown")
        msg_id = m.get("id")
        msg_url = build_message_url(GROUP_ID, msg_id)
        original_ts = str(m.get("date", ""))
        dedupe_key = make_dedupe_key(user_id, text)

        if len(text) >= MEMORY_MIN_LEN and dedupe_key not in existing_memory:
            log_chat_memory(
                user=user,
                user_id=user_id,
                text=text,
                msg_url=msg_url,
                source="history",
                original_ts=original_ts,
            )
            existing_memory.add(dedupe_key)
            memory_inserted += 1

        category = detect_signal(text)
        if category:
            opinions_matched += 1
            if dedupe_key not in existing_opinions:
                log_opinion(
                    user=user,
                    user_id=user_id,
                    text=text,
                    msg_url=msg_url,
                    source="history",
                    original_ts=original_ts,
                    category=category,
                )
                existing_opinions.add(dedupe_key)
                opinions_inserted += 1

    return {
        "source_path": str(resolved_path),
        "total_messages": len(messages),
        "scanned_text_messages": scanned,
        "memory_inserted": memory_inserted,
        "matched_opinions": opinions_matched,
        "inserted_new_opinions": opinions_inserted,
    }
