"""
handlers/messages.py
====================
Handles incoming group and private messages.
"""

import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from core.config import (
    GROUP_ID,
    STRICT_GROUP_ID_FILTER,
    SAVE_ALL_GROUP_TO_MEMORY,
    MUTE_DURATION,
    ADMIN_CHAT_IDS,
)
from core.menus import MAIN_INLINE_MENU
from handlers.admin import publish_announcement
from memory.chat_memory import log_chat_memory
from services.answering import generate_answer
from services.dm import dm_admins
from services.opinions import log_opinion, build_admin_opinion_msg
from services.signals import detect_signal
from utils.helpers import is_admin, is_flood, get_mute_permissions, build_message_url

logger = logging.getLogger(__name__)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main group message handler: flood check -> memory capture -> signal detection."""
    msg = update.message
    if not msg:
        return

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
            logger.warning("Could not mute %s: %s", username, e)
        return

    if user.is_bot or text.startswith("/"):
        return

    msg_url = build_message_url(msg.chat.id, msg.message_id)

    if SAVE_ALL_GROUP_TO_MEMORY:
        log_chat_memory(username, user_id, text, msg_url=msg_url, source="live")

    category = detect_signal(text)
    if not category:
        return

    if not SAVE_ALL_GROUP_TO_MEMORY:
        log_chat_memory(username, user_id, text, msg_url=msg_url, source="live")

    log_opinion(username, user_id, text, msg_url, category=category)
    admin_msg = f"💡 Signal Detected: {category}\n\n{build_admin_opinion_msg(username, text, msg_url)}"

    logger.info("[OPINION] Forwarding signal from %s (%s) [category=%s]", username, user_id, category)
    ok, failures = await dm_admins(context, admin_msg)
    logger.info("[OPINION] Forwarded to %s/%s admins", ok, len(ADMIN_CHAT_IDS))
    if failures:
        logger.warning("[OPINION] Admin DM failures: %s", " | ".join(failures))


async def on_private_ask_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles plain-text messages in private chat.
    - If admin sent announcement text -> publish it
    - If user tapped Ask -> answer question
    """
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
