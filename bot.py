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
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv

from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ChatMemberHandler,
)
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "config" / ".env"

# Prefer config/.env, but keep root .env as a compatibility fallback.
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN        = os.getenv("BOT_TOKEN")           # BotFather token
ADMIN_CHAT_ID    = int(os.getenv("ADMIN_CHAT_ID"))  # Your personal Telegram user ID
GROUP_ID         = int(os.getenv("GROUP_ID"))        # Kickchain group chat ID
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")  # Optional: enables smart opinion detection

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
# OPINION / IDEA DETECTION KEYWORDS
# ─────────────────────────────────────────────
OPINION_KEYWORDS = [
    # Suggestions / ideas
    r"\bshould\b", r"\bcould\b", r"\bwould be (great|nice|cool|better|awesome|good)\b",
    r"\bwhy not\b", r"\bhow about\b", r"\bwhat if\b", r"\bi think\b", r"\bin my opinion\b",
    r"\bimo\b", r"\bimho\b", r"\bsuggestion\b", r"\bsuggest\b", r"\bidea\b",
    r"\bfeature\b", r"\badd\b.*\bgame\b", r"\bplease add\b", r"\bwish\b",
    r"\bneed\b.*\bgame\b", r"\bmissing\b", r"\bwould love\b", r"\bit would be\b",
    # Feedback / complaints
    r"\bproblem\b", r"\bissue\b", r"\bbug\b", r"\bfix\b", r"\bbroken\b",
    r"\bdoesn.t work\b", r"\bnot working\b", r"\bcrash\b",
    # Requests
    r"\bcan you\b", r"\bcan we\b", r"\bwill there be\b", r"\bwhen will\b",
    r"\bplease\b.*\badd\b", r"\bplease\b.*\bchange\b",
    # Positive / negative sentiment about the game
    r"\blike\b.*\bgame\b", r"\blove\b.*\bgame\b", r"\bhate\b.*\bgame\b",
    r"\bdon.t like\b", r"\bnot a fan\b",
    # Gameplay specific
    r"\bphysics\b", r"\bbalance\b", r"\bfair\b", r"\btournament\b",
    r"\bleaderboard\b", r"\brank\b", r"\bmatchmaking\b", r"\blag\b",
]
OPINION_PATTERN = re.compile("|".join(OPINION_KEYWORDS), re.IGNORECASE)

# Minimum message length to consider it an opinion
OPINION_MIN_LEN = 20

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
# flood tracking: {user_id: [timestamp, ...]}
flood_tracker: dict[int, list] = defaultdict(list)

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


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def is_opinion(text: str) -> bool:
    """Return True if the message looks like an opinion or idea."""
    if len(text) < OPINION_MIN_LEN:
        return False
    return bool(OPINION_PATTERN.search(text))


def log_opinion(
    user: str,
    user_id: int,
    text: str,
    msg_url: str = "",
    source: str = "live",
    original_ts: str = "",
):
    """Append opinion to local JSONL file."""
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "user": user,
        "user_id": user_id,
        "text": text,
        "msg_url": msg_url,
        "source": source,
    }
    if original_ts:
        entry["original_ts"] = original_ts
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
        "ts": datetime.utcnow().isoformat(),
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

        if len(text) >= OPINION_MIN_LEN and is_opinion(text):
            opinions_matched += 1
            if dedupe_key not in existing_opinions:
                log_opinion(
                    user=user,
                    user_id=user_id,
                    text=text,
                    msg_url=msg_url,
                    source="history",
                    original_ts=original_ts,
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


def build_admin_opinion_msg(user: str, text: str, msg_url: str = "") -> str:
    link_part = f"\n🔗 [View in group]({msg_url})" if msg_url else ""
    return (
        f"💡 *New Opinion / Idea Detected*\n"
        f"👤 *From:* {user}\n\n"
        f"_{text}_{link_part}"
    )


def is_flood(user_id: int) -> bool:
    """Return True if user has sent too many messages in the flood window."""
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=FLOOD_WINDOW_SEC)
    flood_tracker[user_id] = [t for t in flood_tracker[user_id] if t > cutoff]
    flood_tracker[user_id].append(now)
    return len(flood_tracker[user_id]) > FLOOD_MAX_MSGS


def answer_question_openai(question: str, memory_snippets: list[dict]) -> str:
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
        return resp.choices[0].message.content.strip()
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
        return "🚀 Kickchain V1 is targeting a *March–April 2026* launch. Stay tuned in the channel @kickchainchannel!"

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
    for member in update.message.new_chat_members:
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
        await update.message.reply_text(welcome, parse_mode="Markdown")


async def on_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silent on member leave — no need to call attention to it."""
    pass


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi! I'm the *Kickchain Bot*.\n\n"
        "Here's what I can do:\n"
        "• /ask [question] — Ask anything about Kickchain\n"
        "• /project — Get a quick project summary\n"
        "• /stakes — Stake tiers & rake fees\n"
        "• /referral — Referral & VIP rakeback info\n\n"
        "_I also collect community opinions and send them to the team!_ 💡",
        parse_mode="Markdown",
    )


async def cmd_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *Kickchain — Where Skill Meets Stakes*\n\n"
        "Kickchain is a skill-based 1v1 competitive game built *natively on Telegram*.\n\n"
        "🎮 *Pure Skill* — Physics-based, no RNG, drag-to-aim mechanic\n"
        "💰 *Real Stakes* — USDT/USDC wallets, fully withdrawable\n"
        "🛡️ *Anti-Cheat* — Server-authoritative engine, zero client trust\n"
        "🚫 *No Pay-to-Win* — Cosmetics only, skill decides everything\n\n"
        "📅 *Launch:* March–April 2026\n"
        "📢 Channel: @kickchainchannel",
        parse_mode="Markdown",
    )


async def cmd_stakes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💸 *Stake Tiers & Rake Fees*\n\n"
        "| Tier  | Stakes (USDT) | Rake |\n"
        "|-------|--------------|------|\n"
        "| Micro | $0.05–$0.20  | 8–10%|\n"
        "| Low   | $0.50–$2.00  | 5–6% |\n"
        "| Mid   | $5–$20       | 3–4% |\n"
        "| High  | $50–$200     | 2–2.5%|\n"
        "| VIP 👑| $500–$1,000  | 1–1.5%|\n\n"
        "_Higher volume players get lower rake — whales are retained!_",
        parse_mode="Markdown",
    )


async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤝 *Referral Program*\n\n"
        "Earn a share of your referrals' rake fees:\n"
        "🥉 Bronze → 10% | 🥈 Silver → 15% | 🥇 Gold → 20%\n"
        "💎 Platinum → 25% | 💠 Diamond → 30%\n\n"
        "👑 *VIP Rakeback* (volume-based):\n"
        "Silver 2% → Gold 4% → Platinum 6% → Diamond 8%\n\n"
        "_Every match you play or refer earns you more!_",
        parse_mode="Markdown",
    )


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answer a user question about Kickchain."""
    question = " ".join(context.args).strip() if context.args else ""
    if not question:
        await update.message.reply_text(
            "❓ Usage: `/ask <your question>`\n\nExample: `/ask when does the game launch?`",
            parse_mode="Markdown",
        )
        return

    memory_snippets = retrieve_memory_snippets(question)

    # Try OpenAI first (grounded to KB + memory), then fall back.
    answer = answer_question_openai(question, memory_snippets) or answer_question_basic(question, memory_snippets)
    await update.message.reply_text(answer)


async def cmd_opinions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: show last N collected opinions."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return

    n = int(context.args[0]) if context.args else 10
    try:
        with open(opinions_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        await update.message.reply_text("No opinions logged yet.")
        return

    recent = lines[-n:]
    if not recent:
        await update.message.reply_text("No opinions logged yet.")
        return

    msg = f"📋 *Last {len(recent)} opinions:*\n\n"
    for line in recent:
        try:
            e = json.loads(line)
            msg += f"👤 *{e['user']}* ({e['ts'][:10]})\n_{e['text']}_\n\n"
        except Exception:
            pass

    # Telegram message limit
    if len(msg) > 4000:
        msg = msg[:4000] + "\n_...truncated_"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: show last N remembered chat messages."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return

    n = 10
    if context.args:
        try:
            n = max(1, min(int(context.args[0]), 50))
        except ValueError:
            await update.message.reply_text("Usage: /memory [n]")
            return

    recent = load_recent_memory(limit=n)
    if not recent:
        await update.message.reply_text("No memory saved yet.")
        return

    rows = [f"🧠 Last {len(recent)} memory items:\n"]
    for e in recent:
        user = e.get("user", "unknown")
        ts = str(e.get("original_ts") or e.get("ts", ""))[:19]
        text = normalize_text(e.get("text", ""))[:120]
        rows.append(f"• [{ts}] {user}: {text}")

    msg = "\n".join(rows)
    if len(msg) > 4000:
        msg = msg[:4000] + "\n...truncated"
    await update.message.reply_text(msg)


async def cmd_scanhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin-only: backfill memory + opinions from Telegram exported history.

    Usage:
      /scanhistory
      /scanhistory config/group_history_export.json
      /scanhistory "C:/.../ChatExport_2026-03-01/messages.html"
      /scanhistory config/group_history_export.json 5000
    """
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Admin only command.")
        return

    export_path = context.args[0] if len(context.args) >= 1 else DEFAULT_HISTORY_EXPORT_PATH
    limit = 0
    if len(context.args) >= 2:
        try:
            limit = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Usage: /scanhistory [path] [limit]")
            return

    try:
        stats = scan_history_export(export_path, limit)
    except FileNotFoundError:
        await update.message.reply_text(
            f"❌ Export file not found: `{export_path}`\n"
            "Place Telegram export JSON there or pass a custom path.",
            parse_mode="Markdown",
        )
        return
    except json.JSONDecodeError:
        await update.message.reply_text(
            f"❌ Invalid JSON in file: `{export_path}`",
            parse_mode="Markdown",
        )
        return
    except Exception as e:
        logger.exception("History scan failed")
        await update.message.reply_text(f"❌ Scan failed: {e}")
        return

    await update.message.reply_text(
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
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message to ban them.")
        return
    target = update.message.reply_to_message.from_user
    await context.bot.ban_chat_member(update.effective_chat.id, target.id)
    await update.message.reply_text(f"🚫 {target.full_name} has been banned.")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: mute a user by reply (1 hour default)."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message to mute them.")
        return
    target = update.message.reply_to_message.from_user
    until = datetime.utcnow() + timedelta(hours=1)
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        target.id,
        ChatPermissions(can_send_messages=False),
        until_date=until,
    )
    await update.message.reply_text(f"🔇 {target.full_name} has been muted for 1 hour.")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: unmute a user by reply."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to a user's message to unmute them.")
        return
    target = update.message.reply_to_message.from_user
    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        target.id,
        ChatPermissions(
            can_send_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        ),
    )
    await update.message.reply_text(f"🔊 {target.full_name} has been unmuted.")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main message handler:
    1. Anti-flood check
    2. Opinion/idea extraction → forward to admin
    """
    msg = update.message
    if not msg or not msg.text:
        return

    # Only process target group messages for moderation/memory/opinion extraction.
    if msg.chat.id != GROUP_ID:
        return

    user = msg.from_user
    if not user:
        return

    text = msg.text.strip()
    user_id = user.id
    username = user.username or user.full_name or str(user_id)

    # ── 1. ANTI-FLOOD ─────────────────────────────────────────
    if user_id != ADMIN_CHAT_ID and is_flood(user_id):
        try:
            until = datetime.utcnow() + timedelta(seconds=MUTE_DURATION)
            await context.bot.restrict_chat_member(
                msg.chat.id,
                user_id,
                ChatPermissions(can_send_messages=False),
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

    # ── 2. MEMORY CAPTURE ─────────────────────────────────────
    log_chat_memory(username, user_id, text, msg_url=msg_url, source="live")

    # ── 3. OPINION EXTRACTION ─────────────────────────────────
    if len(text) < OPINION_MIN_LEN:
        return

    if is_opinion(text):
        log_opinion(username, user_id, text, msg_url)

        admin_msg = build_admin_opinion_msg(username, text, msg_url)
        try:
            await context.bot.send_message(
                ADMIN_CHAT_ID,
                admin_msg,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"Failed to forward opinion to admin: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set in config/.env")
    if not ADMIN_CHAT_ID:
        raise ValueError("ADMIN_CHAT_ID not set in config/.env")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_start))
    app.add_handler(CommandHandler("project",  cmd_project))
    app.add_handler(CommandHandler("stakes",   cmd_stakes))
    app.add_handler(CommandHandler("referral", cmd_referral))
    app.add_handler(CommandHandler("ask",      cmd_ask))
    app.add_handler(CommandHandler("opinions", cmd_opinions))
    app.add_handler(CommandHandler("memory",   cmd_memory))
    app.add_handler(CommandHandler("scanhistory", cmd_scanhistory))
    app.add_handler(CommandHandler("ban",      cmd_ban))
    app.add_handler(CommandHandler("mute",     cmd_mute))
    app.add_handler(CommandHandler("unmute",   cmd_unmute))

    # New/left members
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_member))

    # All text messages (opinion detection + flood control)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("🚀 Kickchain Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
