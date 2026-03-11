"""
handlers/members.py
===================
Handles group member join and leave events.
Update the welcome message here.
"""

from telegram import Update
from telegram.ext import ContextTypes


async def on_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome new members with a project intro."""
    msg = update.message
    if not msg:
        return
    for member in msg.new_chat_members:
        name    = member.full_name or member.username or "friend"
        welcome = (
            f"👋 Welcome to *Kickchain*, {name}! ⚽🔗\n\n"
            "If you've ever played *Soccer Stars*, you already know the mechanic — "
            "but Kickchain takes it further:\n\n"
            "🎮 *Pure Skill* — Drag-to-aim, turn-based, zero RNG\n"
            "💰 *Real Stakes* — Play for USDT/USDC, fully withdrawable\n"
            "🛡️ *Anti-Cheat* — Server-authoritative engine, aimbots don't work here\n"
            "🚫 *No Pay-to-Win* — Skill decides everything\n\n"
            "📅 *V1 Launch:* March–April 2026\n\n"
            "❓ Ask anything with /ask\n"
            "📌 Check the pinned message for the full project overview\n"
            "💬 Share your ideas — every voice shapes the game!\n\n"
            "_Let's build something great together. Game on!_ 🚀"
        )
        await msg.reply_text(welcome, parse_mode="Markdown")


async def on_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silent on member leave."""
    pass
