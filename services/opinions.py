"""
services/opinions.py
====================
Opinion/signal JSONL storage and aggregation helpers.
"""

import json
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.config import SIGNAL_SUMMARY_EXAMPLES_PER_CATEGORY, SIGNAL_SUMMARY_WINDOW_HOURS
from utils.helpers import normalize_text, make_dedupe_key

BASE_DIR = Path(__file__).resolve().parent.parent
OPINIONS_LOG_PATH = BASE_DIR / "opinions.jsonl"



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

        text = normalize_text(str(entry.get("text", "")))
        if text and len(examples_by_category[category]) < SIGNAL_SUMMARY_EXAMPLES_PER_CATEGORY:
            examples_by_category[category].append(text[:140])

    sorted_categories = dict(sorted(by_category.items(), key=lambda item: item[1], reverse=True))

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
