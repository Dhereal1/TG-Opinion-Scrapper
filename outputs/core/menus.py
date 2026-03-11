"""
core/menus.py
=============
All Telegram keyboard/button definitions and static reply text constants.
Update this file to change UI labels, button layouts, or static messages.
"""

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ─────────────────────────────────────────────
# BUTTON LABELS
# ─────────────────────────────────────────────
ASK_BTN      = "🎯 Ask Kickchain"
PROJECT_BTN  = "📌 Project"
STAKES_BTN   = "💸 Stakes"
REFERRAL_BTN = "🤝 Referral"
MENU_BTN     = "🧭 Menu"

# ─────────────────────────────────────────────
# CALLBACK DATA KEYS
# ─────────────────────────────────────────────
CB_ASK      = "menu_ask"
CB_PROJECT  = "menu_project"
CB_STAKES   = "menu_stakes"
CB_REFERRAL = "menu_referral"

# ─────────────────────────────────────────────
# KEYBOARDS
# ─────────────────────────────────────────────
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [ASK_BTN, PROJECT_BTN],
        [STAKES_BTN, REFERRAL_BTN],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Use buttons to explore Kickchain",
)

MAIN_INLINE_MENU = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🎯 Ask",      callback_data=CB_ASK),
            InlineKeyboardButton("📌 Project",  callback_data=CB_PROJECT),
        ],
        [
            InlineKeyboardButton("💸 Stakes",   callback_data=CB_STAKES),
            InlineKeyboardButton("🤝 Referral", callback_data=CB_REFERRAL),
        ],
    ]
)

# ─────────────────────────────────────────────
# STATIC REPLY TEXTS
# ─────────────────────────────────────────────
START_TEXT = (
    "👋 Hi! I'm the *Kickchain Bot*.\n\n"
    "Here's what I can do:\n"
    "• /ask [question] — Ask anything about Kickchain\n"
    "• /project — Get a quick project summary\n"
    "• /stakes — Stake tiers & rake fees\n"
    "• /referral — Referral & VIP rakeback info\n"
    "• /announce <text> — Admin: post announcement to configured channels\n\n"
    "Use the buttons below for quick actions.\n\n"
    "_I also collect community opinions and send them to the team!_ 💡"
)

PROJECT_TEXT = (
    "⚽ *Kickchain — Where Skill Meets Stakes*\n\n"
    "The first truly skill-based 1v1 competitive game built *natively on Telegram*.\n"
    "Inspired by Soccer Stars — but with real money, zero RNG, and no pay-to-win.\n\n"
    "🎮 *Drag-to-aim* physics mechanic, turn-based, heavy puck feel\n"
    "💰 *Real Stakes* — USDT/USDC wallets, fully withdrawable winnings\n"
    "🛡️ *Server-authoritative anti-cheat* — aimbots are completely ineffective\n"
    "🏆 *Two economies* — Free Fun Mode + Real Stakes Mode\n"
    "🤝 *Referral system* — earn up to 30% of your referrals' rake fees\n\n"
    "📅 *V1 Launch:* March–April 2026\n"
    "📢 Channel: @KickchainChannel\n"
    "🎮 Play now: https://unique-parfait-7f420d.netlify.app/"
)

STAKES_TEXT = (
    "💸 *Stake Tiers & Rake Fees*\n\n"
    "| Tier  | Stakes (USDT) | Rake |\n"
    "|-------|--------------|------|\n"
    "| Micro | $0.05–$0.20  | 8–10%|\n"
    "| Low   | $0.50–$2.00  | 5–6% |\n"
    "| Mid   | $5–$20       | 3–4% |\n"
    "| High  | $50–$200     | 2–2.5%|\n"
    "| VIP 👑| $500–$1,000  | 1–1.5%|\n\n"
    "_Higher volume players get lower rake — whales are retained!_"
)

REFERRAL_TEXT = (
    "🤝 *Referral Program*\n\n"
    "Earn a share of your referrals' rake fees:\n"
    "🥉 Bronze → 10% | 🥈 Silver → 15% | 🥇 Gold → 20%\n"
    "💎 Platinum → 25% | 💠 Diamond → 30%\n\n"
    "👑 *VIP Rakeback* (volume-based):\n"
    "Silver 2% → Gold 4% → Platinum 6% → Diamond 8%\n\n"
    "_Every match you play or refer earns you more!_"
)
