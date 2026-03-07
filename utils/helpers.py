"""
utils/helpers.py
================
Shared utility helpers used across handlers/services.
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from telegram import ChatPermissions

from core.config import ADMIN_CHAT_IDS_SET, FLOOD_MAX_MSGS, FLOOD_WINDOW_SEC

# Flood tracking state: {user_id: [timestamps...]}
flood_tracker: dict[int, list[datetime]] = defaultdict(list)

TOKEN_PATTERN = re.compile(r"\b\w{3,}\b", re.UNICODE)
STOPWORDS = {
    "the", "and", "for", "you", "are", "with", "that", "this", "from", "have", "has",
    "was", "were", "will", "your", "about", "what", "when", "where", "which", "who",
    "why", "how", "can", "could", "would", "should", "into", "they", "them", "their",
    "our", "out", "just", "not", "but", "all", "any", "too", "its", "it's", "than",
    "then", "also", "get", "got", "use", "using", "used", "been", "being", "more",
}


def normalize_text(text: str) -> str:
    return " ".join(str(text).split()).strip()



def make_dedupe_key(user_id: int, text: str) -> str:
    return f"{user_id}::{normalize_text(text).lower()}"



def build_message_url(chat_id: int, message_id: int) -> str:
    if not chat_id or not message_id:
        return ""
    chat_id_str = str(chat_id).replace("-100", "")
    return f"https://t.me/c/{chat_id_str}/{message_id}"



def extract_export_text(raw_text):
    """
    Telegram export messages may store text as:
      - string
      - list of string/dict fragments
    """
    if isinstance(raw_text, str):
        return raw_text

    if not isinstance(raw_text, list):
        return ""

    chunks = []
    for part in raw_text:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, dict):
            piece = part.get("text")
            if isinstance(piece, str):
                chunks.append(piece)
    return "".join(chunks)



def parse_export_user_id(from_id) -> int:
    """Parse Telegram export from_id values like 'user123456789'."""
    if isinstance(from_id, int):
        return from_id
    if isinstance(from_id, str):
        digits = "".join(ch for ch in from_id if ch.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError:
                return 0
    return 0



def tokenize_text(text: str) -> set[str]:
    tokens = {t.lower() for t in TOKEN_PATTERN.findall(text.lower())}
    return {t for t in tokens if t not in STOPWORDS}



def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_CHAT_IDS_SET



def get_mute_permissions() -> ChatPermissions:
    """Compatibility-safe mute permissions for PTB 21.x."""
    return ChatPermissions.no_permissions()



def get_unmute_permissions(chat_permissions: ChatPermissions | None = None) -> ChatPermissions:
    """
    Prefer restoring chat default permissions. If missing, use explicit full
    message permissions for PTB 21.x fields.
    """
    if chat_permissions is not None:
        return chat_permissions
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )



def is_flood(user_id: int) -> bool:
    """Return True if user has sent too many messages in the flood window."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=FLOOD_WINDOW_SEC)
    flood_tracker[user_id] = [t for t in flood_tracker[user_id] if t > cutoff]
    flood_tracker[user_id].append(now)
    return len(flood_tracker[user_id]) > FLOOD_MAX_MSGS
