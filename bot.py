"""
Kickchain Admin Bot
===================
Features:
  - Group moderator (welcome, spam detection, anti-flood)
  - Chat assistant (answers questions about Kickchain using project knowledge)
  - Opinion/Idea extractor → forwards insights to admin in private chat
  
Setup:
  1. pip install python-telegram-bot openai python-dotenv
  2. Fill in config/.env file (see config/.env.example)
  3. python bot.py
"""

import os
import re
import logging
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dotenv import load_dotenv

from telegram import Update, ChatPermissions
from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)
from telegram.error import Forbidden, BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "config" / ".env"

# Prefer config/.env, but keep root .env as a compatibility fallback.
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()


def parse_int_env(name: str, default: int = 0) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logging.warning("Invalid integer for %s: %r", name, raw)
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
                logging.warning("Skipping invalid ADMIN_CHAT_IDS value: %r", val)
                continue
            if admin_id not in ids:
                ids.append(admin_id)
    return ids


def parse_announcement_targets() -> list[int | str]:
    """
    Parse announcement channels from ANNOUNCEMENT_CHANNEL_IDS.
    Supported values (comma separated):
      - channel IDs, e.g. -1001234567890
      - @channel_usernames
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
            logging.warning("Skipping invalid ANNOUNCEMENT_CHANNEL_IDS value: %r", value)
    return targets


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "").strip()   # BotFather token
GROUP_ID       = parse_int_env("GROUP_ID")            # Kickchain group chat ID
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()  # Optional: enables smart opinion detection
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

# Multi-admin support (primary admin kept for backward compatibility).
ADMIN_CHAT_IDS = parse_admin_ids()
ADMIN_CHAT_IDS_SET = set(ADMIN_CHAT_IDS)
ANNOUNCEMENT_TARGETS = parse_announcement_targets()

# Anti-flood settings
FLOOD_MAX_MSGS   = 5     # messages
FLOOD_WINDOW_SEC = 10    # within N seconds → mute
MUTE_DURATION    = 60    # seconds to mute flooder

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# KICKCHAIN KNOWLEDGE BASE  (for /ask command)
# ─────────────────────────────────────────────
KICKCHAIN_KB = """
Kickchain is a skill-based 1v1 competitive gaming platform built natively on Telegram (Telegram Mini App).

CORE CONCEPT:
- Physics-based soccer / puck game inspired by Soccer Stars
- Turn-based system: players take turns shooting with a drag-to-aim mechanic
- No RNG — pure strategy and precision
- Server-authoritative engine: all physics (collisions, friction, goals) computed server-side; client only renders
- Anti-cheat: input validation, anomaly AI, full match replays stored

GAME MODES:
- Fun Mode: off-chain economy with Fun Coins (non-withdrawable). Monetized via ads, in-app purchases, Battle Pass, cosmetics
- Real Stakes Mode: custodial USDT/USDC wallets. Fully withdrawable winnings. Match rake fee taken from pot.

STAKE TIERS (Real Stakes):
- Micro: $0.05–$0.20 → 8–10% rake
- Low: $0.50–$2.00 → 5–6% rake
- Mid: $5–$20 → 3–4% rake
- High: $50–$200 → 2–2.5% rake
- VIP: $500–$1,000 → 1–1.5% rake

REVENUE STREAMS:
- Match Rake (core) — percentage of every pot
- Withdraw fee: flat $0.25 or 0.5% (max $10)
- Tournaments: 10–20% of prize pool
- Battle Pass: $4.99 or $9.99/season (14 or 30 days)
- Cosmetics Shop (puck skins, trails, goal explosions) — 100% margin
- Rewarded Ads (Fun Mode only)

REFERRAL SYSTEM (revenue share for referring users):
- Bronze 10% / Silver 15% / Gold 20% / Platinum 25% / Diamond 30%

VIP RAKEBACK:
- Bronze 0% / Silver 2% / Gold 4% / Platinum 6% / Diamond 8%

TECH STACK:
- Platform: Telegram Mini App (TMA)
- Frontend: Mobile-first adaptive UI (Figma complete)
- Backend: Server-authoritative Node.js engine
- Blockchain: Custodial USDT/USDC wallets

DEVELOPMENT STATUS (as of early 2026):
- Figma Design System: DONE
- Unity Assets in Production: DONE
- Game Economy Fully Designed: DONE
- Backend Authoritative Structure: IN PROGRESS
- Multiplayer Validation Logic: IN PROGRESS
- Target V1 launch: March–April 2026

TEAM:
- CORPMEMBER29 — Tech Lead & Architect (Frontend, Backend, Blockchain)
- ALI RAZA — Art Director & Assets (Unity, Game Art, UX)
- AHMEDBRO — Growth & Acquisition (UA, Community, Marketing)

GO-TO-MARKET:
- 100,000 DM campaign targeting Soccer Stars communities (Telegram, Discord, Reddit, Instagram, Facebook)
- Viral loop: user plays → invites friends → friends play → user earns rake share
"""

# ─────────────────────────────────────────────
# SIGNAL DETECTION (opinions/ideas/feedback)
# ─────────────────────────────────────────────
CATEGORY_PATTERNS_V2: dict[str, re.Pattern[str]] = {
    "idea/suggestion": re.compile(
        r"(\bwhat if\b|\bhow about\b|\bwhy not\b|\bi suggest\b|\bsuggestion\b|\bidea\b|"
        r"\bwould be (great|nice|cool|better)\b|\bplease add\b|\bcan you add\b|\badd\b|\bimplement\b)",
        re.IGNORECASE,
    ),
    "feedback/review": re.compile(
        r"(\bi (like|love|enjoy)\b|\bnot bad\b|\bgreat\b|\bamazing\b|\bawesome\b|"
        r"\bterrible\b|\bbad\b|\bboring\b|\bfun\b|\baddictive\b|\bhuge\b|\bfire\b)",
        re.IGNORECASE,
    ),
    "complaint/bug": re.compile(
        r"(\bbug\b|\bissue\b|\bproblem\b|\bbroken\b|\bnot working\b|\bdoesn.?t work\b|"
        r"\bcrash\b|\blag\b|\bglitch\b|\bfreeze\b|\bhacker(s)?\b|\bhack(ed|ing)?\b|\bcheat\b)",
        re.IGNORECASE,
    ),
    "request/question": re.compile(
        r"(\bcan you\b|\bcan we\b|\bwill there be\b|\bwhen will\b|\bis it possible\b|\bany plan to\b|"
        r"\bwho\b|\bhow long\b|\bapproximately\b)",
        re.IGNORECASE,
    ),
    "demand/validation": re.compile(
        r"(\bif you (get|make|build|fix)\b|\bwe all in\b|\byou already won\b|\bwe need\b|"
        r"\bplayers need\b|\bhuge community\b|\bcommunity\b|\bmany (people|players)\b|\bhonest players\b)",
        re.IGNORECASE,
    ),
    "expectation": re.compile(
        r"(\bas long as\b|\bonly if\b|\bit should\b|\byou should\b|\bmust\b|\bneeds to\b|\bneed to\b)",
        re.IGNORECASE,
    ),
    "competitor insight": re.compile(
        r"(\bminiclip\b|\bsoccer stars\b|\bfifa\b|\bother game\b|\bdevelopers\b|\bprofit\b|\bcoins\b|\bads\b)",
        re.IGNORECASE,
    ),
    "concern/risk": re.compile(
        r"(\bsue\b|\bcopyright\b|\binfring(e|ement)\b|\blegal\b|\bscam\b|\bscamming\b|\bspammer(s)?\b)",
        re.IGNORECASE,
    ),
}

QUESTION_CHARS = {"?", "¿", "؟"}
STRONG_PUNCT = {"!", "‼", "❗", "🔥"}
LOW_SIGNAL_V2 = {
    "nice", "cool", "wow", "great", "amazing", "fire", "gm", "lol", "lmao", "ok", "thanks",
    "thank you", "ty", "grazie", "ciao", "benvenuto", "welcome", "hi", "hello",
}

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
# flood tracking: {user_id: [timestamp, ...]}
flood_tracker: dict[int, list] = defaultdict(list)
last_auto_signal_summary_signature = ""

# collected opinions (in-memory, also logged to opinions.jsonl)
opinions_log_path = BASE_DIR / "opinions.jsonl"
chat_memory_path = BASE_DIR / "memory" / "chat_memory.jsonl"
DEFAULT_HISTORY_EXPORT_PATH = "config/group_history_export.json"
MEMORY_MIN_LEN = 8
MEMORY_TOP_K = 5
MEMORY_CANDIDATE_LIMIT = 2500
TOKEN_PATTERN = re.compile(r"\b\w{3,}\b", re.UNICODE)
STOPWORDS = {
    "the", "and", "for", "you", "are", "with", "that", "this", "from", "have", "has",
    "was", "were", "will", "your", "about", "what", "when", "where", "which", "who",
    "why", "how", "can", "could", "would", "should", "into", "they", "them", "their",
    "our", "out", "just", "not", "but", "all", "any", "too", "its", "it's", "than",
    "then", "also", "get", "got", "use", "using", "used", "been", "being", "more",
}

ASK_BTN = "🎯 Ask Kickchain"
PROJECT_BTN = "📌 Project"
STAKES_BTN = "💸 Stakes"
REFERRAL_BTN = "🤝 Referral"
MENU_BTN = "🧭 Menu"

CB_ASK = "menu_ask"
CB_PROJECT = "menu_project"
CB_STAKES = "menu_stakes"
CB_REFERRAL = "menu_referral"

CB_OP_APPROVE = "op_approve"
CB_OP_REWRITE = "op_rewrite"
CB_OP_IGNORE = "op_ignore"
CB_OP_SAVE = "op_save"

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [ASK_BTN, PROJECT_BTN],
        [STAKES_BTN, REFERRAL_BTN],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Use buttons to explore Kickchain",
)

MAIN_INLINE_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🎯 Ask", callback_data=CB_ASK), InlineKeyboardButton("📌 Project", callback_data=CB_PROJECT)],
        [InlineKeyboardButton("💸 Stakes", callback_data=CB_STAKES), InlineKeyboardButton("🤝 Referral", callback_data=CB_REFERRAL)],
    ]
)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def looks_like_welcome_or_smalltalk(low: str) -> bool:
    return any(
        phrase in low
        for phrase in [
            "welcome to the group",
            "thanks for joining",
            "glad to see you",
            "benvenuto",
            "ciao",
            "grazie",
            "thank you",
            "thanks",
        ]
    )


def detect_signal_v2(text: str) -> str | None:
    """Smarter lightweight classifier: regex first, then punctuation/intent heuristics."""
    t = normalize_text(text)
    if not t:
        return None

    low = t.lower().strip()
    if looks_like_welcome_or_smalltalk(low):
        return None

    if len(t) < 12:
        if any(ch in t for ch in QUESTION_CHARS):
            return "request/question"
        return None

    if low in LOW_SIGNAL_V2:
        return None

    if re.fullmatch(r"[\W_]+", t):
        return None

    priority = [
        "complaint/bug",
        "concern/risk",
        "request/question",
        "idea/suggestion",
        "expectation",
        "demand/validation",
        "competitor insight",
        "feedback/review",
    ]
    for cat in priority:
        if CATEGORY_PATTERNS_V2[cat].search(t):
            return cat

    if any(ch in t for ch in QUESTION_CHARS):
        return "request/question"

    padded_low = f" {low} "
    if (" if " in padded_low or " as long as " in padded_low) and len(t) >= 18:
        return "expectation"

    if any(ch in t for ch in STRONG_PUNCT) and len(t) >= 18:
        return "feedback/review"

    return None


def detect_signal(text: str) -> str | None:
    """Backward-compatible wrapper to use v2 detector everywhere."""
    return detect_signal_v2(text)


def is_opinion(text: str) -> bool:
    """Backward-compatible helper."""
    return detect_signal(text) is not None


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_CHAT_IDS_SET


def get_mute_permissions() -> ChatPermissions:
    """Compatibility-safe mute permissions for PTB 21.x."""
    return ChatPermissions.no_permissions()


def get_unmute_permissions(chat_permissions: ChatPermissions | None = None) -> ChatPermissions:
    """
    Prefer restoring chat default permissions. If missing, use explicit full
    message permissions for PTB 21.6 fields.
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


def generate_answer(question: str) -> str:
    memory_snippets = retrieve_memory_snippets(question)
    return answer_question_openai(question, memory_snippets) or answer_question_basic(question, memory_snippets)


START_TEXT = (
    "👋 Hi! I'm the *Kickchain Bot*.\n\n"
    "Here's what I can do:\n"
    "• /ask [question] — Ask anything about Kickchain\n"
    "• /project — Get a quick project summary\n"
    "• /stakes — Stake tiers & rake fees\n"
    "• /referral — Referral & VIP rakeback info\n"
    "• /announce <text> — Admin: post announcement to configured channels\n\n"
    "Use the buttons below for quick actions.\n\n"
    "_I also collect community opinions and send them to the team!_ 💡"
)

PROJECT_TEXT = (
    "⚽ *Kickchain — Where Skill Meets Stakes*\n\n"
    "Kickchain is a skill-based 1v1 competitive game built *natively on Telegram*.\n\n"
    "🎮 *Pure Skill* — Physics-based, no RNG, drag-to-aim mechanic\n"
    "💰 *Real Stakes* — USDT/USDC wallets, fully withdrawable\n"
    "🛡️ *Anti-Cheat* — Server-authoritative engine, zero client trust\n"
    "🚫 *No Pay-to-Win* — Cosmetics only, skill decides everything\n\n"
    "📅 *Launch:* March–April 2026\n"
    "📢 Channel: @kickchainchannel\n"
    "🎮 Play now: https://unique-parfait-7f420d.netlify.app/"
)

STAKES_TEXT = (
    "💸 *Stake Tiers & Rake Fees*\n\n"
    "| Tier  | Stakes (USDT) | Rake |\n"
    "|-------|--------------|------|\n"
    "| Micro | $0.05–$0.20  | 8–10%|\n"
    "| Low   | $0.50–$2.00  | 5–6% |\n"
    "| Mid   | $5–$20       | 3–4% |\n"
    "| High  | $50–$200     | 2–2.5%|\n"
    "| VIP 👑| $500–$1,000  | 1–1.5%|\n\n"
    "_Higher volume players get lower rake — whales are retained!_"
)

REFERRAL_TEXT = (
    "🤝 *Referral Program*\n\n"
    "Earn a share of your referrals' rake fees:\n"
    "🥉 Bronze → 10% | 🥈 Silver → 15% | 🥇 Gold → 20%\n"
    "💎 Platinum → 25% | 💠 Diamond → 30%\n\n"
    "👑 *VIP Rakeback* (volume-based):\n"
    "Silver 2% → Gold 4% → Platinum 6% → Diamond 8%\n\n"
    "_Every match you play or refer earns you more!_"
)


async def send_main_menu(message):
    await message.reply_text(
        "🧭 *Quick Actions*",
        parse_mode="Markdown",
        reply_markup=MAIN_INLINE_MENU,
    )


async def send_project(message):
    await message.reply_text(PROJECT_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)


async def send_stakes(message):
    await message.reply_text(STAKES_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)


async def send_referral(message):
    await message.reply_text(REFERRAL_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)


def log_opinion(
    user: str,
    user_id: int,
    text: str,
    msg_url: str = "",
    source: str = "live",
    original_ts: str = "",
    category: str = "",
):
    """Append opinion to local JSONL file."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "user_id": user_id,
        "text": text,
        "msg_url": msg_url,
        "source": source,
    }
    if original_ts:
        entry["original_ts"] = original_ts
    if category:
        entry["category"] = category
    with open(opinions_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def extract_export_text(raw_text) -> str:
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


def normalize_text(text: str) -> str:
    return " ".join(str(text).split()).strip()


def make_dedupe_key(user_id: int, text: str) -> str:
    return f"{user_id}::{normalize_text(text).lower()}"


def build_message_url(chat_id: int, message_id: int) -> str:
    if not chat_id or not message_id:
        return ""
    chat_id_str = str(chat_id).replace("-100", "")
    return f"https://t.me/c/{chat_id_str}/{message_id}"


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

    chat_memory_path.parent.mkdir(parents=True, exist_ok=True)
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

    with open(chat_memory_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_existing_keys(file_path: Path) -> set[str]:
    """Load stable keys from JSONL files for dedupe."""
    keys = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    key = make_dedupe_key(int(e.get("user_id", 0)), str(e.get("text", "")))
                    keys.add(key)
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return keys


def load_existing_opinion_keys() -> set[str]:
    """Used to avoid duplicate opinion backfill entries across multiple scans."""
    return load_existing_keys(Path(opinions_log_path))


def load_existing_memory_keys() -> set[str]:
    """Used to avoid duplicate memory entries across multiple scans."""
    return load_existing_keys(chat_memory_path)


def resolve_export_json_path(export_path: str) -> Path:
    """
    Accepts either a JSON export path directly, or messages.html path and
    auto-resolves sibling result.json (Telegram Desktop export layout).
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


def tokenize_text(text: str) -> set[str]:
    tokens = {t.lower() for t in TOKEN_PATTERN.findall(text.lower())}
    return {t for t in tokens if t not in STOPWORDS}


def load_recent_memory(limit: int = MEMORY_CANDIDATE_LIMIT) -> list[dict]:
    """Load recent memory entries from JSONL."""
    if limit <= 0:
        return []

    recent_lines: deque[str] = deque(maxlen=limit)
    try:
        with open(chat_memory_path, "r", encoding="utf-8") as f:
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


def scan_history_export(export_path: str, limit: int = 0) -> dict:
    """
    Scan Telegram exported history and backfill memory + detected opinions.
    Telegram bot API does not provide full historical fetch, so this is the
    practical way to process older messages.
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


def parse_iso_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def collect_signal_stats(window_hours: int) -> dict:
    """
    Summarize categorized signals from opinions.jsonl for the given time window.
    """
    window_hours = max(1, int(window_hours))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    by_category: dict[str, int] = defaultdict(int)
    examples_by_category: dict[str, list[str]] = defaultdict(list)
    unique_users: set[int] = set()
    newest_ts = ""
    total = 0

    recent_lines: deque[str] = deque(maxlen=12000)
    try:
        with open(opinions_log_path, "r", encoding="utf-8") as f:
            for line in f:
                recent_lines.append(line)
    except FileNotFoundError:
        return {
            "window_hours": window_hours,
            "total": 0,
            "unique_users": 0,
            "by_category": {},
            "examples_by_category": {},
            "newest_ts": "",
        }

    for line in recent_lines:
        try:
            entry = json.loads(line)
        except Exception:
            continue

        category = str(entry.get("category", "")).strip().lower()
        if not category:
            continue

        ts_value = str(entry.get("ts", "")).strip()
        ts = parse_iso_ts(ts_value)
        if ts is None or ts < cutoff:
            continue

        total += 1
        by_category[category] += 1
        if ts_value > newest_ts:
            newest_ts = ts_value

        user_id_raw = entry.get("user_id")
        if isinstance(user_id_raw, int):
            unique_users.add(user_id_raw)

        text = normalize_text(str(entry.get("text", "")))
        if text and len(examples_by_category[category]) < SIGNAL_SUMMARY_EXAMPLES_PER_CATEGORY:
            examples_by_category[category].append(text[:140])

    sorted_categories = dict(
        sorted(by_category.items(), key=lambda item: item[1], reverse=True)
    )

    return {
        "window_hours": window_hours,
        "total": total,
        "unique_users": len(unique_users),
        "by_category": sorted_categories,
        "examples_by_category": dict(examples_by_category),
        "newest_ts": newest_ts,
    }


def build_signal_summary_text(stats: dict, title: str = "📊 Signal Summary") -> str:
    window_hours = int(stats.get("window_hours", SIGNAL_SUMMARY_WINDOW_HOURS))
    total = int(stats.get("total", 0))
    unique_users = int(stats.get("unique_users", 0))
    by_category: dict[str, int] = stats.get("by_category", {})
    examples_by_category: dict[str, list[str]] = stats.get("examples_by_category", {})

    if total <= 0:
        return f"{title} (last {window_hours}h)\nNo signals captured in this window."

    lines = [
        f"{title} (last {window_hours}h)",
        f"Total signals: {total}",
        f"Unique users: {unique_users}",
        "",
        "By category:",
    ]
    for category, count in by_category.items():
        lines.append(f"- {category}: {count}")
        examples = examples_by_category.get(category, [])
        if examples:
            lines.append(f"  e.g. {examples[0]}")

    out = "\n".join(lines).strip()
    if len(out) > 3900:
        out = out[:3900] + "\n...truncated"
    return out


def build_signal_summary_signature(stats: dict) -> str:
    parts = [
        str(stats.get("window_hours", "")),
        str(stats.get("total", "")),
        str(stats.get("unique_users", "")),
        str(stats.get("newest_ts", "")),
    ]
    by_category = stats.get("by_category", {})
    parts.extend(f"{k}:{v}" for k, v in sorted(by_category.items()))
    return "|".join(parts)


async def maybe_send_auto_signal_summary(context: ContextTypes.DEFAULT_TYPE):
    global last_auto_signal_summary_signature

    stats = collect_signal_stats(SIGNAL_SUMMARY_WINDOW_HOURS)
    total = int(stats.get("total", 0))
    if total < SIGNAL_SUMMARY_MIN_COUNT:
        logger.info(
            "[SUMMARY] Skipping auto-summary (total=%s < min=%s)",
            total,
            SIGNAL_SUMMARY_MIN_COUNT,
        )
        return

    signature = build_signal_summary_signature(stats)
    if signature == last_auto_signal_summary_signature:
        logger.info("[SUMMARY] Skipping auto-summary (no new signal changes)")
        return

    text = build_signal_summary_text(stats, title="📊 Auto Signal Summary")
    ok, failures = await dm_admins(context, text)
    logger.info("[SUMMARY] Auto-summary sent to %s/%s admins", ok, len(ADMIN_CHAT_IDS))
    if failures:
        logger.warning("[SUMMARY] Auto-summary DM failures: %s", " | ".join(failures))

    last_auto_signal_summary_signature = signature


async def job_signal_summary(context: ContextTypes.DEFAULT_TYPE):
    await maybe_send_auto_signal_summary(context)


def build_admin_opinion_msg(user: str, text: str, msg_url: str = "") -> str:
    lines = [
        "💡 New Opinion / Idea Detected",
        f"👤 From: {user}",
        "",
        text,
    ]
    if msg_url:
        lines.extend(["", f"🔗 View in group: {msg_url}"])
    return "\n".join(lines)


async def dm_admins(context: ContextTypes.DEFAULT_TYPE, text: str) -> tuple[int, list[str]]:
    """
    Send a private DM to all configured admins and return (success_count, failures).
    Failures include readable reasons to simplify runtime troubleshooting.
    """
    ok = 0
    failures: list[str] = []
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                disable_web_page_preview=True,
            )
            ok += 1
        except Forbidden as e:
            reason = (
                "bot cannot DM this user yet (admin must open bot and press Start)"
            )
            logger.error("Failed to DM admin %s: %s (%s)", admin_id, e, reason)
            failures.append(f"{admin_id}: {reason}")
        except BadRequest as e:
            logger.error("Failed to DM admin %s: %s", admin_id, e)
            failures.append(f"{admin_id}: bad request ({e})")
        except Exception as e:
            logger.error("Failed to DM admin %s: %s", admin_id, e)
            failures.append(f"{admin_id}: {e}")
    return ok, failures


def is_flood(user_id: int) -> bool:
    """Return True if user has sent too many messages in the flood window."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=FLOOD_WINDOW_SEC)
    flood_tracker[user_id] = [t for t in flood_tracker[user_id] if t > cutoff]
    flood_tracker[user_id].append(now)
    return len(flood_tracker[user_id]) > FLOOD_MAX_MSGS


def answer_question_openai(question: str, memory_snippets: list[dict]) -> str | None:
    """Use OpenAI with strict grounding: KB + retrieved memory snippets only."""
    if not OPENAI_API_KEY:
        return None
    try:
        memory_context = format_memory_context(memory_snippets)
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the official assistant for Kickchain, a skill-based "
                        "1v1 competitive gaming platform on Telegram.\n"
                        "Rules:\n"
                        "1) Answer using ONLY the evidence provided below.\n"
                        "2) Do not invent facts.\n"
                        "3) If evidence is missing or uncertain, say clearly: "
                        "'I don't have enough confirmed info from saved docs/chat memory yet.'\n"
                        "4) Keep answers concise and practical.\n\n"
                        f"KNOWLEDGE BASE:\n{KICKCHAIN_KB}\n\n"
                        f"COMMUNITY MEMORY SNIPPETS:\n{memory_context}"
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=300,
            temperature=0.4,
        )
        content = resp.choices[0].message.content
        return content.strip() if content else None
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return None


def answer_question_basic(question: str, memory_snippets: list[dict]) -> str:
    """Fallback answer: memory-first, then simple keyword-based KB rules."""
    if memory_snippets:
        lines = []
        for s in memory_snippets[:3]:
            user = s.get("user", "unknown")
            ts = s.get("original_ts") or s.get("ts", "")
            text = normalize_text(s.get("text", ""))[:180]
            lines.append(f"- [{ts}] {user}: {text}")
        return (
            "🧠 Based on saved community chat memory, here are the most relevant messages:\n"
            + "\n".join(lines)
            + "\n\nIf you need official confirmation, check pinned docs or ask the admin."
        )

    q = question.lower()

    if any(w in q for w in ["launch", "release", "when", "ready"]):
        return (
            "🚀 Kickchain V1 is targeting a *March–April 2026* launch. "
            "Stay tuned in the channel @kickchainchannel!\n"
            "🎮 Play now: https://unique-parfait-7f420d.netlify.app/"
        )

    if any(w in q for w in ["stake", "money", "usdt", "usdc", "real money", "withdraw"]):
        return (
            "💰 Kickchain's *Real Stakes* mode uses custodial USDT/USDC wallets. "
            "Winnings are fully withdrawable. Stake tiers range from *Micro ($0.05)* to *VIP ($1,000)*. "
            "A small rake fee is taken per match."
        )

    if any(w in q for w in ["hack", "cheat", "aimbot", "script"]):
        return (
            "🛡️ Kickchain uses a *server-authoritative engine*. "
            "The server runs all physics — clients only send input vectors. "
            "Aimbots and client-side scripts are completely ineffective here!"
        )

    if any(w in q for w in ["referral", "invite", "earn"]):
        return (
            "🤝 The *Referral System* lets you earn a share of your referrals' rake fees: "
            "Bronze 10% → Diamond 30%. Invite friends and earn passively!"
        )

    if any(w in q for w in ["tournament", "tournaments"]):
        return (
            "🏆 *Tournaments* are structured high-prize events. "
            "The platform reserves 10–20% of the prize pool. Entry fees apply."
        )

    if any(w in q for w in ["free", "fun mode", "no money", "without money"]):
        return (
            "🎮 *Fun Mode* is completely free! You play with Fun Coins (non-withdrawable) "
            "and earn rewards via daily login, ads, and the Battle Pass."
        )

    if any(w in q for w in ["battle pass", "season"]):
        return "🎫 *Battle Pass* costs $4.99 (14 days) or $9.99 (30 days) per season and unlocks exclusive cosmetics & rewards."

    if any(w in q for w in ["team", "who made", "developer", "founder"]):
        return (
            "👥 *The Kickchain Team:*\n"
            "• CORPMEMBER29 — Tech Lead & Architect\n"
            "• ALI RAZA — Art Director & Assets\n"
            "• AHMEDBRO — Growth & Acquisition"
        )

    return (
        "🤖 Good question! I don't have a specific answer for that. "
        "Feel free to ping the admin directly or check the pinned message for the full whitepaper. "
        "You can also ask in the group — the team reads everything! ⚽"
    )


# ─────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────

async def on_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members."""
    msg = update.message
    if not msg:
        return

    for member in msg.new_chat_members:
        name = member.full_name or member.username or "friend"
        welcome = (
            f"👋 Welcome to *Kickchain*, {name}! ⚽🔗\n\n"
            "We're building the first *skill-based 1v1 competitive gaming layer* on Telegram — "
            "where skill meets stakes.\n\n"
            "📌 Check the *pinned message* for the full project overview.\n"
            "❓ Ask anything with /ask — our bot knows the project inside out!\n"
            "💬 Share your ideas, feedback or suggestions — every voice shapes the game!\n\n"
            "_Let's build something great together. Game on!_ 🚀"
        )
        await msg.reply_text(welcome, parse_mode="Markdown")


async def on_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silent on member leave — no need to call attention to it."""
    pass


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    await msg.reply_text(
        START_TEXT,
        parse_mode="Markdown",
        reply_markup=MAIN_INLINE_MENU,
    )


async def cmd_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await send_project(msg)


async def cmd_stakes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await send_stakes(msg)


async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await send_referral(msg)


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer a user question about Kickchain."""
    msg = update.message
    if not msg:
        return

    args = context.args or []
    question = " ".join(args).strip()
    if not question:
        await msg.reply_text(
            "❓ Usage: `/ask <your question>`\n\nExample: `/ask when does the game launch?`",
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return

    answer = generate_answer(question)
    await msg.reply_text(answer, reply_markup=MAIN_INLINE_MENU)


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await send_main_menu(msg)


async def cmd_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: publish an announcement to configured channels."""
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return

    if not is_admin(user.id):
        await msg.reply_text("⛔ Admin only command.")
        return

    if not ANNOUNCEMENT_TARGETS:
        await msg.reply_text(
            "❌ No announcement channels configured.\n"
            "Set `ANNOUNCEMENT_CHANNEL_IDS` in config/.env.",
            parse_mode="Markdown",
        )
        return

    args = context.args or []
    text = " ".join(args).strip()
    if not text and msg.reply_to_message and msg.reply_to_message.text:
        text = msg.reply_to_message.text.strip()

    if not text:
        user_data = context.user_data
        if user_data is not None:
            user_data["awaiting_announcement_text"] = True
        await msg.reply_text(
            "📢 Announcement prompt enabled.\n"
            "Send your announcement text now in *private chat* with the bot.\n\n"
            "You can still use: /announce <message>",
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return

    await publish_announcement(context, msg, text)


async def publish_announcement(context: ContextTypes.DEFAULT_TYPE, reply_message, text: str):
    ok = 0
    failed: list[str] = []
    announcement_text = f"📢 Announcement\n\n{text}\n\n🎮 Play now: https://unique-parfait-7f420d.netlify.app/"
    for target in ANNOUNCEMENT_TARGETS:
        try:
            await context.bot.send_message(chat_id=target, text=announcement_text, reply_markup=MAIN_INLINE_MENU)
            ok += 1
        except Exception as e:
            failed.append(f"{target}: {e}")

    result_text = f"✅ Announcement sent to {ok}/{len(ANNOUNCEMENT_TARGETS)} channel(s)."
    if failed:
        result_text += "\n\nFailed:\n" + "\n".join(failed[:3])
    await reply_message.reply_text(result_text, reply_markup=MAIN_INLINE_MENU)


async def on_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle UI button clicks for primary user actions."""
    msg = update.message
    if not msg or not hasattr(msg, 'text') or not msg.text:
        return

    text = msg.text.strip()

    if text == PROJECT_BTN:
        await send_project(msg)
        return

    if text == STAKES_BTN:
        await send_stakes(msg)
        return

    if text == REFERRAL_BTN:
        await send_referral(msg)
        return

    if text == ASK_BTN:
        user_data = context.user_data
        if user_data is None:
            return
        user_data["awaiting_ask_question"] = True
        # Use reply_text if available, else fallback to send_message
        if hasattr(msg, 'reply_text'):
            await msg.reply_text(
                "❓ Send your question now and I'll answer it.",
                reply_markup=MAIN_INLINE_MENU,
            )
        else:
            await context.bot.send_message(
                chat_id=msg.chat.id,
                text="❓ Send your question now and I'll answer it.",
                reply_markup=MAIN_INLINE_MENU,
            )
        return

    if text == MENU_BTN:
        await send_main_menu(msg)
        return


async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    user_data = context.user_data
    if user_data is None:
        return
    msg = query.message
    chat_id = msg.chat.id if msg else query.from_user.id

    if query.data == CB_PROJECT:
        await context.bot.send_message(
            chat_id=chat_id,
            text=PROJECT_TEXT,
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return
    if query.data == CB_STAKES:
        await context.bot.send_message(
            chat_id=chat_id,
            text=STAKES_TEXT,
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return
    if query.data == CB_REFERRAL:
        await context.bot.send_message(
            chat_id=chat_id,
            text=REFERRAL_TEXT,
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return
    if query.data == CB_ASK:
        user_data["awaiting_ask_question"] = True
        await context.bot.send_message(
            chat_id=chat_id,
            text="❓ Send your question now and I'll answer it.",
            reply_markup=MAIN_INLINE_MENU,
        )
        return


async def on_private_ask_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Accept plain-text questions after user taps Ask button in private chat."""
    msg = update.message
    if not msg or not msg.text:
        return
    chat = update.effective_chat
    if not chat or chat.type != "private":
        return
    user_data = context.user_data
    if not user_data:
        return

    text = msg.text.strip()
    if not text or text.startswith("/"):
        return

    user = update.effective_user
    if user and is_admin(user.id) and user_data.get("awaiting_announcement_text"):
        user_data["awaiting_announcement_text"] = False
        await publish_announcement(context, msg, text)
        return

    if not user_data.get("awaiting_ask_question"):
        return

    user_data["awaiting_ask_question"] = False
    answer = generate_answer(text)
    await msg.reply_text(answer, reply_markup=MAIN_INLINE_MENU)


async def cmd_signalsummary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: summarize categorized signal volume in the last N hours."""
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return

    if not is_admin(user.id):
        await msg.reply_text("⛔ Admin only command.")
        return

    window_hours = SIGNAL_SUMMARY_WINDOW_HOURS
    args = context.args or []
    if args:
        try:
            window_hours = max(1, min(int(args[0]), 168))
        except ValueError:
            await msg.reply_text("Usage: /signalsummary [hours]")
            return

    stats = collect_signal_stats(window_hours)
    text = build_signal_summary_text(stats)
    await msg.reply_text(text)


async def cmd_opinions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: show last N collected opinions."""
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return

    if not is_admin(user.id):
        await msg.reply_text("⛔ Admin only command.")
        return

    args = context.args or []
    if args:
        try:
            n = max(1, min(int(args[0]), 50))
        except ValueError:
            await msg.reply_text("Usage: /opinions [n]")
            return
    else:
        n = 10

    try:
        with open(opinions_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        await msg.reply_text("No opinions logged yet.")
        return

    recent = lines[-n:]
    if not recent:
        await msg.reply_text("No opinions logged yet.")
        return

    response = [f"📋 Last {len(recent)} opinions:\n"]
    for line in recent:
        try:
            e = json.loads(line)
            user_label = str(e.get("user", "unknown"))
            ts = str(e.get("ts", ""))[:10]
            text = normalize_text(str(e.get("text", "")))
            response.append(f"👤 {user_label} ({ts})")
            response.append(text)
            response.append("")
        except Exception:
            pass

    out = "\n".join(response).strip()
    # Telegram message limit
    if len(out) > 4000:
        out = out[:4000] + "\n...truncated"
    await msg.reply_text(out)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: show last N remembered chat messages."""
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return

    if not is_admin(user.id):
        await msg.reply_text("⛔ Admin only command.")
        return

    n = 10
    args = context.args or []
    if args:
        try:
            n = max(1, min(int(args[0]), 50))
        except ValueError:
            await msg.reply_text("Usage: /memory [n]")
            return

    recent = load_recent_memory(limit=n)
    if not recent:
        await msg.reply_text("No memory saved yet.")
        return

    rows = [f"🧠 Last {len(recent)} memory items:\n"]
    for e in recent:
        user = e.get("user", "unknown")
        ts = str(e.get("original_ts") or e.get("ts", ""))[:19]
        text = normalize_text(e.get("text", ""))[:120]
        rows.append(f"• [{ts}] {user}: {text}")

    out = "\n".join(rows)
    if len(out) > 4000:
        out = out[:4000] + "\n...truncated"
    await msg.reply_text(out)


async def cmd_scanhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin-only: backfill memory + opinions from Telegram exported history.

    Usage:
      /scanhistory
      /scanhistory config/group_history_export.json
      /scanhistory "C:/.../ChatExport_2026-03-01/messages.html"
      /scanhistory config/group_history_export.json 5000
    """
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return

    if not is_admin(user.id):
        await msg.reply_text("⛔ Admin only command.")
        return

    args = context.args or []
    export_path = args[0] if len(args) >= 1 else DEFAULT_HISTORY_EXPORT_PATH
    limit = 0
    if len(args) >= 2:
        try:
            limit = max(0, int(args[1]))
        except ValueError:
            await msg.reply_text("Usage: /scanhistory [path] [limit]")
            return

    try:
        stats = scan_history_export(export_path, limit)
    except FileNotFoundError:
        await msg.reply_text(
            f"❌ Export file not found: `{export_path}`\n"
            "Place Telegram export JSON there or pass a custom path.",
            parse_mode="Markdown",
        )
        return
    except json.JSONDecodeError:
        await msg.reply_text(
            f"❌ Invalid JSON in file: `{export_path}`",
            parse_mode="Markdown",
        )
        return
    except Exception as e:
        logger.exception("History scan failed")
        await msg.reply_text(f"❌ Scan failed: {e}")
        return

    await msg.reply_text(
        "✅ *History Scan Complete*\n\n"
        f"• Source file: `{stats['source_path']}`\n"
        f"• Total messages loaded: *{stats['total_messages']}*\n"
        f"• Text messages scanned: *{stats['scanned_text_messages']}*\n"
        f"• New memory rows inserted: *{stats['memory_inserted']}*\n"
        f"• Opinion matches: *{stats['matched_opinions']}*\n"
        f"• New opinions inserted: *{stats['inserted_new_opinions']}*",
        parse_mode="Markdown",
    )


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: ban a user by reply."""
    msg = update.message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user or not chat:
        return
    if not is_admin(user.id):
        return
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a user's message to ban them.")
        return
    target = msg.reply_to_message.from_user
    if not target:
        await msg.reply_text("Couldn't identify that user to ban.")
        return
    await context.bot.ban_chat_member(chat.id, target.id)
    await msg.reply_text(f"🚫 {target.full_name} has been banned.")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: mute a user by reply (1 hour default)."""
    msg = update.message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user or not chat:
        return
    if not is_admin(user.id):
        return
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a user's message to mute them.")
        return
    target = msg.reply_to_message.from_user
    if not target:
        await msg.reply_text("Couldn't identify that user to mute.")
        return
    until = datetime.now(timezone.utc) + timedelta(hours=1)
    await context.bot.restrict_chat_member(
        chat.id,
        target.id,
        get_mute_permissions(),
        until_date=until,
    )
    await msg.reply_text(f"🔇 {target.full_name} has been muted for 1 hour.")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: unmute a user by reply."""
    msg = update.message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user or not chat:
        return
    if not is_admin(user.id):
        return
    if not msg.reply_to_message:
        await msg.reply_text("Reply to a user's message to unmute them.")
        return
    target = msg.reply_to_message.from_user
    if not target:
        await msg.reply_text("Couldn't identify that user to unmute.")
        return
    await context.bot.restrict_chat_member(
        chat.id,
        target.id,
        get_unmute_permissions(getattr(chat, "permissions", None)),
    )
    await msg.reply_text(f"🔊 {target.full_name} has been unmuted.")


async def cmd_testdm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: verify bot can DM all admins."""
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return
    if not is_admin(user.id):
        await msg.reply_text("⛔ Admin only command.")
        return

    test_text = (
        "✅ Admin DM test from Kickchain bot.\n"
        "If you can read this, private DM delivery is working."
    )
    ok, failures = await dm_admins(context, test_text)
    response = [f"DM test result: {ok}/{len(ADMIN_CHAT_IDS)} delivered."]
    if failures:
        response.append("")
        response.append("Failures:")
        response.extend(failures[:5])
    await msg.reply_text("\n".join(response), reply_markup=MAIN_INLINE_MENU)


async def post_init(app: Application):
    """Set bot command menu shown in Telegram UI."""
    commands = [
        BotCommand("start", "Open bot menu"),
        BotCommand("menu", "Show quick action buttons"),
        BotCommand("ask", "Ask anything about Kickchain"),
        BotCommand("project", "Project summary"),
        BotCommand("stakes", "Stake tiers and rake"),
        BotCommand("referral", "Referral and VIP rakeback"),
        BotCommand("announce", "Admin: post to announcement channels"),
        BotCommand("signalsummary", "Admin: summarize recent signal trends"),
        BotCommand("opinions", "Admin: view collected opinions"),
        BotCommand("memory", "Admin: view saved chat memory"),
        BotCommand("scanhistory", "Admin: import history export"),
        BotCommand("testdm", "Admin: test private DMs"),
    ]
    await app.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await app.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
    await app.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main message handler:
    1. Anti-flood check
    2. Opinion/idea extraction → forward to admin
    """
    msg = update.message
    if not msg:
        return

    # Process group/supergroup chats. If GROUP_ID is set, enforce it.
    if msg.chat.type not in {"group", "supergroup"}:
        return
    if STRICT_GROUP_ID_FILTER and GROUP_ID and msg.chat.id != GROUP_ID:
        return

    user = msg.from_user
    if not user:
        return

    raw_text = msg.text or msg.caption or ""
    text = raw_text.strip()
    if not text:
        return
    user_id = user.id
    username = user.username or user.full_name or str(user_id)

    # ── 1. ANTI-FLOOD ─────────────────────────────────────────
    if not is_admin(user_id) and is_flood(user_id):
        try:
            until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_DURATION)
            await context.bot.restrict_chat_member(
                msg.chat.id,
                user_id,
                get_mute_permissions(),
                until_date=until,
            )
            await msg.reply_text(
                f"⚠️ @{username}, you've been muted for {MUTE_DURATION}s for flooding. "
                "Please keep the chat clean!"
            )
        except Exception as e:
            logger.warning(f"Could not mute {username}: {e}")
        return

    # Skip bot messages/commands for memory + opinion processing.
    if user.is_bot or text.startswith("/"):
        return

    msg_url = build_message_url(msg.chat.id, msg.message_id)

    # Optional memory capture for all group text.
    if SAVE_ALL_GROUP_TO_MEMORY:
        log_chat_memory(username, user_id, text, msg_url=msg_url, source="live")

    # Signal-only forwarding (opinions/ideas/feedback/complaints/review).
    category = detect_signal(text)
    if not category:
        return

    # If not saving all memory, still keep signal messages in memory.
    if not SAVE_ALL_GROUP_TO_MEMORY:
        log_chat_memory(username, user_id, text, msg_url=msg_url, source="live")

    log_opinion(username, user_id, text, msg_url, category=category)
    admin_msg = build_admin_opinion_msg(username, text, msg_url)
    admin_msg = f"💡 Signal Detected: {category}\n\n{admin_msg}"

    logger.info(
        "[OPINION] Forwarding signal from %s (%s) [category=%s]",
        username,
        user_id,
        category,
    )
    logger.info(f"[OPINION] Attempting to send to admins: {ADMIN_CHAT_IDS}")
    ok, failures = await dm_admins(context, admin_msg)
    logger.info("[OPINION] Forwarded to %s/%s admins", ok, len(ADMIN_CHAT_IDS))
    if failures:
        logger.warning("[OPINION] Admin DM failures: %s", " | ".join(failures))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set in config/.env")
    if not ADMIN_CHAT_IDS:
        raise ValueError(
            "No admin IDs configured. Set ADMIN_CHAT_ID and optional SECOND_ADMIN_CHAT_ID "
            "or ADMIN_CHAT_IDS in config/.env"
        )

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_start))
    app.add_handler(CommandHandler("menu",     cmd_menu))
    app.add_handler(CommandHandler("project",  cmd_project))
    app.add_handler(CommandHandler("stakes",   cmd_stakes))
    app.add_handler(CommandHandler("referral", cmd_referral))
    app.add_handler(CommandHandler("ask",      cmd_ask))
    app.add_handler(CommandHandler("announce", cmd_announce))
    app.add_handler(CommandHandler("signalsummary", cmd_signalsummary))
    app.add_handler(CommandHandler("opinions", cmd_opinions))
    app.add_handler(CommandHandler("memory",   cmd_memory))
    app.add_handler(CommandHandler("scanhistory", cmd_scanhistory))
    app.add_handler(CommandHandler("testdm",   cmd_testdm))
    app.add_handler(CommandHandler("ban",      cmd_ban))
    app.add_handler(CommandHandler("mute",     cmd_mute))
    app.add_handler(CommandHandler("unmute",   cmd_unmute))

    # UI button handlers
    app.add_handler(
        MessageHandler(
            filters.Regex(
                rf"^({re.escape(ASK_BTN)}|{re.escape(PROJECT_BTN)}|{re.escape(STAKES_BTN)}|{re.escape(REFERRAL_BTN)}|{re.escape(MENU_BTN)})$"
            ),
            on_menu_button,
        )
    )
    app.add_handler(CallbackQueryHandler(on_menu_callback, pattern=r"^menu_"))
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, on_private_ask_input)
    )

    # New/left members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))

    # Group messages/captions (opinion detection + flood control)
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, on_message))

    if AUTO_SIGNAL_SUMMARY and app.job_queue:
        interval = timedelta(minutes=SIGNAL_SUMMARY_INTERVAL_MINUTES)
        app.job_queue.run_repeating(
            job_signal_summary,
            interval=interval,
            first=interval,
            name="auto_signal_summary",
        )
        logger.info(
            "[SUMMARY] Auto signal summary enabled: every %sm, window=%sh, min_count=%s",
            SIGNAL_SUMMARY_INTERVAL_MINUTES,
            SIGNAL_SUMMARY_WINDOW_HOURS,
            SIGNAL_SUMMARY_MIN_COUNT,
        )

    logger.info("🚀 Kickchain Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
