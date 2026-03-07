"""
handlers/moderation.py
======================
Admin moderation commands: /ban /mute /unmute.
"""

from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from utils.helpers import is_admin, get_mute_permissions, get_unmute_permissions


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
