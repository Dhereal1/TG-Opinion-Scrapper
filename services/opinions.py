"""
services/opinions.py
====================
Opinion/signal JSONL storage and aggregation helpers.
"""

import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.config import SIGNAL_SUMMARY_EXAMPLES_PER_CATEGORY, SIGNAL_SUMMARY_WINDOW_HOURS
from utils.helpers import normalize_text, make_dedupe_key

BASE_DIR = Path(__file__).resolve().parent.parent
OPINIONS_LOG_PATH = BASE_DIR / "opinions.jsonl"

CATEGORY_STYLE: dict[str, tuple[str, str]] = {
    "idea/suggestion": ("💡", "Product Suggestion"),
    "feedback/review": ("🧾", "Player Feedback"),
    "complaint/bug": ("🚨", "Issue / Bug Report"),
    "request/question": ("❓", "Question / Clarification"),
    "demand/validation": ("📣", "Market Demand Signal"),
    "expectation": ("📐", "Expectation / Condition"),
    "competitor insight": ("🔍", "Competitor Insight"),
    "concern/risk": ("⚠️", "Risk / Trust Concern"),
}

POSITIVE_WORDS = {
    "great", "good", "love", "amazing", "awesome", "fun", "smooth", "excellent",
    "nice", "perfect", "best", "enjoy",
}
NEGATIVE_WORDS = {
    "bad", "terrible", "boring", "broken", "bug", "issue", "problem", "lag",
    "glitch", "scam", "fraud", "slow", "annoying", "frustrating",
}


def _category_style(category: str) -> tuple[str, str]:
    key = normalize_text(category).lower()
    if key in CATEGORY_STYLE:
        return CATEGORY_STYLE[key]
    title = key.title() if key else "Community Signal"
    return "💡", title


def _classify_sentiment(text: str) -> tuple[str, str]:
    low = normalize_text(text).lower()
    pos = sum(1 for w in POSITIVE_WORDS if re.search(rf"\b{re.escape(w)}\b", low))
    neg = sum(1 for w in NEGATIVE_WORDS if re.search(rf"\b{re.escape(w)}\b", low))
    if neg > pos and neg > 0:
        return "🔴", "Negative"
    if pos > neg and pos > 0:
        return "🟢", "Positive"
    return "🟡", "Neutral"


def _excerpt(text: str, max_chars: int = 220) -> str:
    clean = normalize_text(text)
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "…"



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

    with open(OPINIONS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")



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



def load_existing_opinion_keys() -> set[str]:
    """Used to avoid duplicate opinion backfill entries across multiple scans."""
    keys = set()
    try:
        with open(OPINIONS_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    keys.add(make_dedupe_key(int(e.get("user_id", 0)), str(e.get("text", ""))))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return keys



def collect_signal_stats(window_hours: int) -> dict:
    """Summarize categorized signals from opinions.jsonl for a given window."""
    window_hours = max(1, int(window_hours))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    by_category: dict[str, int] = defaultdict(int)
    examples_by_category: dict[str, list[str]] = defaultdict(list)
    users_by_category_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    unique_users: set[int] = set()
    newest_ts = ""
    total = 0

    recent_lines: deque[str] = deque(maxlen=12000)
    try:
        with open(OPINIONS_LOG_PATH, "r", encoding="utf-8") as f:
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

        user_label = normalize_text(str(entry.get("user", ""))).strip() or "unknown"
        users_by_category_count[category][user_label] += 1

        text = normalize_text(str(entry.get("text", "")))
        if text and len(examples_by_category[category]) < SIGNAL_SUMMARY_EXAMPLES_PER_CATEGORY:
            examples_by_category[category].append(_excerpt(text, max_chars=150))

    sorted_categories = dict(sorted(by_category.items(), key=lambda item: item[1], reverse=True))
    users_by_category: dict[str, list[str]] = {}
    for category, counts in users_by_category_count.items():
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
        users_by_category[category] = [name for name, _ in ranked[:3]]

    return {
        "window_hours": window_hours,
        "total": total,
        "unique_users": len(unique_users),
        "by_category": sorted_categories,
        "examples_by_category": dict(examples_by_category),
        "users_by_category": users_by_category,
        "newest_ts": newest_ts,
    }



def build_signal_summary_text(stats: dict, title: str = "📊 Signal Summary") -> str:
    window_hours = int(stats.get("window_hours", SIGNAL_SUMMARY_WINDOW_HOURS))
    total = int(stats.get("total", 0))
    unique_users = int(stats.get("unique_users", 0))
    by_category: dict[str, int] = stats.get("by_category", {})
    examples_by_category: dict[str, list[str]] = stats.get("examples_by_category", {})
    users_by_category: dict[str, list[str]] = stats.get("users_by_category", {})

    if total <= 0:
        return f"{title} (last {window_hours}h)\nNo signals captured in this window."

    lines = [
        f"{title} (last {window_hours}h)",
        f"Signals: {total} | Active users: {unique_users}",
        "",
        "Category breakdown:",
    ]
    for category, count in by_category.items():
        icon, label = _category_style(category)
        pct = round((count / total) * 100) if total else 0
        lines.append(f"{icon} {label}: {count} ({pct}%)")
        users = users_by_category.get(category, [])
        if users:
            lines.append(f"Users: {', '.join(users)}")
        examples = examples_by_category.get(category, [])
        if examples:
            lines.append(f"Excerpt: \"{examples[0]}\"")
        lines.append("")

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



def build_admin_opinion_msg(user: str, text: str, msg_url: str = "", category: str = "") -> str:
    icon, label = _category_style(category)
    sentiment_icon, sentiment_label = _classify_sentiment(text)
    snippet = _excerpt(text, max_chars=320)
    lines = [
        f"{icon} {label}",
        "────────────────────────────",
        f"👤 {user}",
        f"{sentiment_icon} Sentiment: {sentiment_label}",
        "",
        f"💬 \"{snippet}\"",
    ]
    if msg_url:
        lines.extend(["", f"🔗 {msg_url}"])
    return "\n".join(lines)
