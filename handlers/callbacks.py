"""
handlers/callbacks.py
=====================
Handles inline callbacks and menu button presses.
"""

from telegram import Update
from telegram.ext import ContextTypes

from core.menus import (
    ASK_BTN,
    PROJECT_BTN,
    STAKES_BTN,
    REFERRAL_BTN,
    MENU_BTN,
    PROJECT_TEXT,
    STAKES_TEXT,
    REFERRAL_TEXT,
    CB_ASK,
    CB_PROJECT,
    CB_STAKES,
    CB_REFERRAL,
    MAIN_INLINE_MENU,
)


async def on_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses (pattern: menu_*)."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    user_data = context.user_data
    msg = query.message
    chat_id = msg.chat.id if msg else query.from_user.id

    if query.data == CB_PROJECT:
        await context.bot.send_message(
            chat_id=chat_id,
            text=PROJECT_TEXT,
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return

    if query.data == CB_STAKES:
        await context.bot.send_message(
            chat_id=chat_id,
            text=STAKES_TEXT,
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return

    if query.data == CB_REFERRAL:
        await context.bot.send_message(
            chat_id=chat_id,
            text=REFERRAL_TEXT,
            parse_mode="Markdown",
            reply_markup=MAIN_INLINE_MENU,
        )
        return

    if query.data == CB_ASK:
        if user_data is not None:
            user_data["awaiting_ask_question"] = True
        await context.bot.send_message(
            chat_id=chat_id,
            text="❓ Send your question now and I'll answer it.",
            reply_markup=MAIN_INLINE_MENU,
        )


async def on_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reply keyboard button taps."""
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()

    if text == PROJECT_BTN:
        await msg.reply_text(PROJECT_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)
        return

    if text == STAKES_BTN:
        await msg.reply_text(STAKES_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)
        return

    if text == REFERRAL_BTN:
        await msg.reply_text(REFERRAL_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)
        return

    if text == ASK_BTN:
        user_data = context.user_data
        if user_data is not None:
            user_data["awaiting_ask_question"] = True
        await msg.reply_text(
            "❓ Send your question now and I'll answer it.",
            reply_markup=MAIN_INLINE_MENU,
        )
        return

    if text == MENU_BTN:
        await msg.reply_text("🧭 *Quick Actions*", parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)
