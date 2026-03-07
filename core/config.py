"""
core/config.py
==============
All environment variable parsing and global configuration constants.
Edit this file to change bot-wide settings.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / "config" / ".env"

# Prefer config/.env, fallback to root .env
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

logger = logging.getLogger(__name__)


# -----------------------------
# PARSING HELPERS
# -----------------------------

def parse_int_env(name: str, default: int = 0) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s: %r", name, raw)
        return default



def parse_bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "y"}



def parse_admin_ids() -> list[int]:
    """
    Supported config patterns:
      1) ADMIN_CHAT_ID + optional SECOND_ADMIN_CHAT_ID
      2) ADMIN_CHAT_IDS=111,222,333 (comma-separated)
    """
    ids: list[int] = []

    primary = parse_int_env("ADMIN_CHAT_ID")
    secondary = parse_int_env("SECOND_ADMIN_CHAT_ID")
    if primary:
        ids.append(primary)
    if secondary and secondary != primary:
        ids.append(secondary)

    raw_list = str(os.getenv("ADMIN_CHAT_IDS", "")).strip()
    if raw_list:
        for chunk in raw_list.split(","):
            val = chunk.strip()
            if not val:
                continue
            try:
                admin_id = int(val)
            except ValueError:
                logger.warning("Skipping invalid ADMIN_CHAT_IDS value: %r", val)
                continue
            if admin_id not in ids:
                ids.append(admin_id)
    return ids



def parse_announcement_targets() -> list[int | str]:
    """
    Parse announcement channels from ANNOUNCEMENT_CHANNEL_IDS.
    Supports numeric IDs and @usernames (comma-separated).
    """
    raw = str(os.getenv("ANNOUNCEMENT_CHANNEL_IDS", "")).strip()
    targets: list[int | str] = []
    if not raw:
        return targets

    for chunk in raw.split(","):
        value = chunk.strip()
        if not value:
            continue
        if value.startswith("@"):
            targets.append(value)
            continue
        try:
            targets.append(int(value))
        except ValueError:
            logger.warning("Skipping invalid ANNOUNCEMENT_CHANNEL_IDS value: %r", value)
    return targets


# -----------------------------
# BOT CONFIG
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROUP_ID = parse_int_env("GROUP_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

STRICT_GROUP_ID_FILTER = parse_bool_env("STRICT_GROUP_ID_FILTER", False)
SAVE_ALL_GROUP_TO_MEMORY = parse_bool_env("SAVE_ALL_GROUP_TO_MEMORY", True)
AUTO_SIGNAL_SUMMARY = parse_bool_env("AUTO_SIGNAL_SUMMARY", True)

SIGNAL_SUMMARY_WINDOW_HOURS = max(1, parse_int_env("SIGNAL_SUMMARY_WINDOW_HOURS", 2))
SIGNAL_SUMMARY_INTERVAL_MINUTES = max(5, parse_int_env("SIGNAL_SUMMARY_INTERVAL_MINUTES", 120))
SIGNAL_SUMMARY_MIN_COUNT = max(1, parse_int_env("SIGNAL_SUMMARY_MIN_COUNT", 3))
SIGNAL_SUMMARY_EXAMPLES_PER_CATEGORY = max(
    1,
    min(3, parse_int_env("SIGNAL_SUMMARY_EXAMPLES_PER_CATEGORY", 2)),
)

# Anti-flood settings
FLOOD_MAX_MSGS = 5
FLOOD_WINDOW_SEC = 10
MUTE_DURATION = 60

# Admin IDs
ADMIN_CHAT_IDS = parse_admin_ids()
ADMIN_CHAT_IDS_SET = set(ADMIN_CHAT_IDS)

# Announcement targets
ANNOUNCEMENT_TARGETS = parse_announcement_targets()

# File paths
DEFAULT_HISTORY_EXPORT_PATH = "config/group_history_export.json"
