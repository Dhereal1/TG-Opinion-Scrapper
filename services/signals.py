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

CATEGORY_IDEA = "idea/suggestion"
CATEGORY_FEEDBACK = "feedback/review"
CATEGORY_BUG = "complaint/bug"
CATEGORY_QUESTION = "request/question"
CATEGORY_DEMAND = "demand/validation"
CATEGORY_EXPECTATION = "expectation"
CATEGORY_COMPETITOR = "competitor insight"
CATEGORY_RISK = "concern/risk"

MIN_SIGNAL_CHARS = 30
MIN_SIGNAL_WORDS = 5

CATEGORY_PATTERNS_V2: dict[str, re.Pattern[str]] = {
    CATEGORY_IDEA: re.compile(
        r"(\bwhat if\b|\bhow about\b|\bwhy not\b|\bi suggest\b|\bmy suggestion\b|\bfeature request\b|"
        r"\bidea\b|\bplease add\b|\bcan you add\b|\byou should add\b|\bconsider adding\b|"
        r"\bwould love to see\b|\bit would be (great|better|useful)\b)",
        re.IGNORECASE,
    ),
    CATEGORY_FEEDBACK: re.compile(
        r"(\bi (like|love|enjoy|prefer)\b|\bin my opinion\b|\boverall\b|\bthis is (great|good|bad|boring|fun)\b|"
        r"\bfeels (great|good|bad|slow)\b|\bvery (good|bad|fun|smooth|laggy)\b)",
        re.IGNORECASE,
    ),
    CATEGORY_BUG: re.compile(
        r"(\bbug\b|\bissue\b|\bproblem\b|\bbroken\b|\bnot working\b|\bdoesn.?t work\b|"
        r"\bcrash(ed|ing|es)?\b|\blag(gy)?\b|\bglitch\b|\bfreeze\b|\bstuck\b|"
        r"\bhacker(s)?\b|\bhack(ed|ing)?\b|\bcheat(ing)?\b|\bexploit\b)",
        re.IGNORECASE,
    ),
    CATEGORY_QUESTION: re.compile(
        r"(\bcan you\b|\bcould you\b|\bcan we\b|\bwill there be\b|\bwhen (will|is)\b|"
        r"\bis it possible\b|\bany plan to\b|\bdo you plan\b|\bhow (do|does|can|long)\b|"
        r"\bwhat (is|are)\b|\bwhere (is|can)\b|\bwhy (is|does)\b|\bwho (is|are)\b)",
        re.IGNORECASE,
    ),
    CATEGORY_DEMAND: re.compile(
        r"(\bif you (get|make|build|fix)\b|\bwe all in\b|\byou already won\b|\bwe need\b|"
        r"\bplayers need\b|\bcommunity needs\b|\bmany (people|players)\b|\beveryone wants\b|"
        r"\bthis will bring\b|\bmass adoption\b)",
        re.IGNORECASE,
    ),
    CATEGORY_EXPECTATION: re.compile(
        r"(\bas long as\b|\bonly if\b|\bit should\b|\byou should\b|\bmust\b|\bneeds to\b|\bneed to\b)",
        re.IGNORECASE,
    ),
    CATEGORY_COMPETITOR: re.compile(
        r"(\bminiclip\b|\bsoccer stars\b|\bfifa\b|\bother game\b|\banother game\b|\bcompetitor(s)?\b|"
        r"\bblack market\b|\bofficial store\b|\bapp store\b|\bplay store\b|\bcompared to\b|"
        r"\bcompare(d)? with\b|\bcheaper than\b|\bpricing model\b|\bcoin price\b|\btoken price\b)",
        re.IGNORECASE,
    ),
    CATEGORY_RISK: re.compile(
        r"(\bsue\b|\bcopyright\b|\binfring(e|ement)\b|\blegal\b|\bscam\b|\bscamming\b|"
        r"\bfraud\b|\bsuspicious\b|\bunsafe\b|\bspammer(s)?\b)",
        re.IGNORECASE,
    ),
}

QUESTION_CHARS = {"?", "¿", "؟"}
STRONG_PUNCT = {"!", "‼", "❗", "🔥"}
LOW_SIGNAL_V2 = {
    "nice", "cool", "wow", "great", "amazing", "fire", "gm", "lol", "lmao", "ok", "okay", "thanks",
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


def _word_count(text: str) -> int:
    return len(re.findall(r"[a-zA-Z0-9_']+", text))



def detect_signal(text: str) -> str | None:
    """Classify a message into a signal category, or return None."""
    t = normalize_text(text)
    low = t.lower().strip()

    if not t:
        return None
    if _looks_like_smalltalk(low):
        return None
    if len(t) < MIN_SIGNAL_CHARS:
        return None
    if _word_count(low) < MIN_SIGNAL_WORDS:
        return None
    if low in LOW_SIGNAL_V2:
        return None
    if re.fullmatch(r"[\W_]+", t):
        return None

    priority = [
        CATEGORY_BUG,
        CATEGORY_RISK,
        CATEGORY_COMPETITOR,
        CATEGORY_QUESTION,
        CATEGORY_IDEA,
        CATEGORY_EXPECTATION,
        CATEGORY_DEMAND,
        CATEGORY_FEEDBACK,
    ]
    for cat in priority:
        if CATEGORY_PATTERNS_V2[cat].search(t):
            return cat

    if any(ch in t for ch in QUESTION_CHARS):
        return CATEGORY_QUESTION

    padded = f" {low} "
    if (" if " in padded or " as long as " in padded) and len(t) >= 18:
        return CATEGORY_EXPECTATION
    if any(ch in t for ch in STRONG_PUNCT) and len(t) >= 18:
        return CATEGORY_FEEDBACK

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
