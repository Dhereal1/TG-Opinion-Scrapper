"""
services/signals.py
===================
Signal/opinion detection and scheduled signal summary job.
"""

import re
import logging

from telegram.ext import ContextTypes

from core.config import SIGNAL_SUMMARY_WINDOW_HOURS, SIGNAL_SUMMARY_MIN_COUNT, ADMIN_CHAT_IDS
from services.opinions import (
    collect_signal_stats,
    build_signal_summary_text,
    build_signal_summary_signature,
)
from services.dm import dm_admins
from utils.helpers import normalize_text

logger = logging.getLogger(__name__)

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


def _looks_like_smalltalk(low: str) -> bool:
    return any(
        phrase in low
        for phrase in [
            "welcome to the group", "thanks for joining", "glad to see you",
            "benvenuto", "ciao", "grazie", "thank you", "thanks",
        ]
    )



def detect_signal(text: str) -> str | None:
    """Classify a message into a signal category, or return None."""
    t = normalize_text(text)
    low = t.lower().strip()

    if not t:
        return None
    if _looks_like_smalltalk(low):
        return None
    if len(t) < 12:
        return "request/question" if any(ch in t for ch in QUESTION_CHARS) else None
    if low in LOW_SIGNAL_V2:
        return None
    if re.fullmatch(r"[\W_]+", t):
        return None

    priority = [
        "complaint/bug", "concern/risk", "request/question", "idea/suggestion",
        "expectation", "demand/validation", "competitor insight", "feedback/review",
    ]
    for cat in priority:
        if CATEGORY_PATTERNS_V2[cat].search(t):
            return cat

    if any(ch in t for ch in QUESTION_CHARS):
        return "request/question"

    padded = f" {low} "
    if (" if " in padded or " as long as " in padded) and len(t) >= 18:
        return "expectation"
    if any(ch in t for ch in STRONG_PUNCT) and len(t) >= 18:
        return "feedback/review"

    return None


_last_summary_signature = ""


async def job_signal_summary(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job: send signal summary to admins if new signals exist."""
    global _last_summary_signature

    stats = collect_signal_stats(SIGNAL_SUMMARY_WINDOW_HOURS)
    total = int(stats.get("total", 0))
    if total < SIGNAL_SUMMARY_MIN_COUNT:
        logger.info("[SUMMARY] Skipping auto-summary (total=%s < min=%s)", total, SIGNAL_SUMMARY_MIN_COUNT)
        return

    signature = build_signal_summary_signature(stats)
    if signature == _last_summary_signature:
        logger.info("[SUMMARY] Skipping auto-summary (no new signal changes)")
        return

    text = build_signal_summary_text(stats, title="📊 Auto Signal Summary")
    ok, failures = await dm_admins(context, text)
    logger.info("[SUMMARY] Auto-summary sent to %s/%s admins", ok, len(ADMIN_CHAT_IDS))
    if failures:
        logger.warning("[SUMMARY] Auto-summary DM failures: %s", " | ".join(failures))

    _last_summary_signature = signature
