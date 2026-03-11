"""
core/setup.py
=============
Registers Telegram bot command menus shown in chat UI.
"""

from telegram import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)
from telegram.ext import Application


async def post_init(app: Application):
    commands = [
        BotCommand("start", "Open bot menu"),
        BotCommand("menu", "Show quick action buttons"),
        BotCommand("ask", "Ask anything about Kickchain"),
        BotCommand("project", "Project summary"),
        BotCommand("stakes", "Stake tiers and rake"),
        BotCommand("referral", "Referral and VIP rakeback"),
        BotCommand("announce", "Admin: post to announcement channels"),
        BotCommand("signalsummary", "Admin: summarize recent signal trends"),
        BotCommand("opinions", "Admin: view collected opinions"),
        BotCommand("memory", "Admin: view saved chat memory"),
        BotCommand("scanhistory", "Admin: import history export"),
        BotCommand("testdm", "Admin: test private DMs"),
        BotCommand("uploadkb", "Admin: upload and apply KB document"),
    ]
    await app.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await app.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
    await app.bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
