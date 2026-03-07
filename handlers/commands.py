"""
handlers/commands.py
====================
User-facing command handlers.
"""

from telegram import Update
from telegram.ext import ContextTypes

from core.menus import (
    START_TEXT,
    PROJECT_TEXT,
    STAKES_TEXT,
    REFERRAL_TEXT,
    MAIN_INLINE_MENU,
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    await msg.reply_text(
        START_TEXT,
        parse_mode="Markdown",
        reply_markup=MAIN_INLINE_MENU,
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text("🧭 *Quick Actions*", parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)


async def cmd_project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(PROJECT_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)


async def cmd_stakes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(STAKES_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)


async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    await msg.reply_text(REFERRAL_TEXT, parse_mode="Markdown", reply_markup=MAIN_INLINE_MENU)
