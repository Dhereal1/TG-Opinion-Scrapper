"""
handlers/members.py
===================
Member join/leave event handlers.
"""

from telegram import Update
from telegram.ext import ContextTypes


async def on_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members."""
    msg = update.message
    if not msg:
        return

    for member in msg.new_chat_members:
        name = member.full_name or member.username or "friend"
        welcome = (
            f"👋 Welcome to *Kickchain*, {name}! ⚽🔗\n\n"
            "We're building the first *skill-based 1v1 competitive gaming layer* on Telegram - "
            "where skill meets stakes.\n\n"
            "📌 Check the *pinned message* for the full project overview.\n"
            "❓ Ask anything with /ask - our bot knows the project inside out!\n"
            "💬 Share your ideas, feedback or suggestions - every voice shapes the game!\n\n"
            "_Let's build something great together. Game on!_ 🚀"
        )
        await msg.reply_text(welcome, parse_mode="Markdown")


async def on_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silent on member leave."""
    return
