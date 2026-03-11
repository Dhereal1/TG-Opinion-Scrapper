"""
Kickchain Admin Bot — Entry Point
==================================
Run with: python bot.py
"""

import logging
import re
from datetime import timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from core.config import BOT_TOKEN, ADMIN_CHAT_IDS, AUTO_SIGNAL_SUMMARY
from core.config import SIGNAL_SUMMARY_INTERVAL_MINUTES, SIGNAL_SUMMARY_WINDOW_HOURS, SIGNAL_SUMMARY_MIN_COUNT
from core.menus import ASK_BTN, PROJECT_BTN, STAKES_BTN, REFERRAL_BTN, MENU_BTN
from core.setup import post_init

from handlers.commands import cmd_start, cmd_menu, cmd_project, cmd_stakes, cmd_referral
from handlers.ask import cmd_ask
from handlers.admin import (
    cmd_announce, cmd_signalsummary, cmd_opinions,
    cmd_memory, cmd_scanhistory, cmd_testdm,
)
from handlers.moderation import cmd_ban, cmd_mute, cmd_unmute
from handlers.messages import on_message, on_private_ask_input
from handlers.callbacks import on_menu_callback, on_menu_button
from handlers.members import on_new_member, on_left_member
from handlers.kb_upload import (
    cmd_uploadkb, on_document_upload, on_kb_callback,
    CB_KB_CONFIRM, CB_KB_CANCEL,
)
from services.signals import job_signal_summary

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set in config/.env")
    if not ADMIN_CHAT_IDS:
        raise ValueError(
            "No admin IDs configured. Set ADMIN_CHAT_ID and optional SECOND_ADMIN_CHAT_ID "
            "or ADMIN_CHAT_IDS in config/.env"
        )

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ── User Commands ──────────────────────────────
    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_start))
    app.add_handler(CommandHandler("menu",     cmd_menu))
    app.add_handler(CommandHandler("project",  cmd_project))
    app.add_handler(CommandHandler("stakes",   cmd_stakes))
    app.add_handler(CommandHandler("referral", cmd_referral))
    app.add_handler(CommandHandler("ask",      cmd_ask))

    # ── Admin Commands ─────────────────────────────
    app.add_handler(CommandHandler("announce",      cmd_announce))
    app.add_handler(CommandHandler("signalsummary", cmd_signalsummary))
    app.add_handler(CommandHandler("opinions",      cmd_opinions))
    app.add_handler(CommandHandler("memory",        cmd_memory))
    app.add_handler(CommandHandler("scanhistory",   cmd_scanhistory))
    app.add_handler(CommandHandler("testdm",        cmd_testdm))
    app.add_handler(CommandHandler("uploadkb",      cmd_uploadkb))

    # ── Moderation Commands ────────────────────────
    app.add_handler(CommandHandler("ban",    cmd_ban))
    app.add_handler(CommandHandler("mute",   cmd_mute))
    app.add_handler(CommandHandler("unmute", cmd_unmute))

    # ── Inline Button Callbacks ────────────────────
    app.add_handler(CallbackQueryHandler(on_kb_callback,   pattern=f"^({CB_KB_CONFIRM}|{CB_KB_CANCEL})$"))
    app.add_handler(CallbackQueryHandler(on_menu_callback, pattern=r"^menu_"))

    # ── Reply Keyboard Buttons ─────────────────────
    app.add_handler(
        MessageHandler(
            filters.Regex(
                rf"^({re.escape(ASK_BTN)}|{re.escape(PROJECT_BTN)}|{re.escape(STAKES_BTN)}"
                rf"|{re.escape(REFERRAL_BTN)}|{re.escape(MENU_BTN)})$"
            ),
            on_menu_button,
        )
    )

    # ── Private Chat Handlers ──────────────────────
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.Document.ALL,
            on_document_upload,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            on_private_ask_input,
        )
    )

    # ── Member Events ──────────────────────────────
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER,  on_left_member))

    # ── Group Message Handler ──────────────────────
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND, on_message))

    # ── Scheduled Jobs ─────────────────────────────
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
