"""
handlers/ask.py
===============
Handles the /ask command.
"""

from telegram import Update
from telegram.ext import ContextTypes

from core.menus import MAIN_INLINE_MENU
from services.answering import generate_answer


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    args = context.args or []
    question = " ".join(args).strip()

    if not question:
        await msg.reply_text(
            "❓ Usage: `/ask <your question>`\n\nExample: `/ask when does the game launch?`",
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return

    answer = generate_answer(question)
    await msg.reply_text(answer, reply_markup=MAIN_INLINE_MENU)
