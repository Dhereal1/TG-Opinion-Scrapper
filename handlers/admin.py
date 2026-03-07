"""
handlers/admin.py
=================
Admin-only command handlers.
"""

import json
import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.config import (
    ANNOUNCEMENT_TARGETS,
    SIGNAL_SUMMARY_WINDOW_HOURS,
    DEFAULT_HISTORY_EXPORT_PATH,
    ADMIN_CHAT_IDS,
)
from core.menus import MAIN_INLINE_MENU
from memory.chat_memory import load_recent_memory
from services.dm import dm_admins
from services.history import scan_history_export
from services.opinions import (
    OPINIONS_LOG_PATH,
    build_signal_summary_text,
    collect_signal_stats,
)
from utils.helpers import is_admin, normalize_text

logger = logging.getLogger(__name__)


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
        with open(OPINIONS_LOG_PATH, "r", encoding="utf-8") as f:
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
        user_name = e.get("user", "unknown")
        ts = str(e.get("original_ts") or e.get("ts", ""))[:19]
        text = normalize_text(e.get("text", ""))[:120]
        rows.append(f"• [{ts}] {user_name}: {text}")

    out = "\n".join(rows)
    if len(out) > 4000:
        out = out[:4000] + "\n...truncated"
    await msg.reply_text(out)


async def cmd_scanhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin-only: backfill memory + opinions from Telegram exported history.
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
