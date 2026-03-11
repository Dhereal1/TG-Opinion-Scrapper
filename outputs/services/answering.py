"""
services/answering.py
=====================
Question answering for the /ask command.

Priority order:
  1. KB keyword rules  — instant, no API, covers all known topics
  2. OpenAI GPT-4o-mini — full KB + memory context (if API key set)
  3. Memory snippets   — last resort only, never overrides KB

To improve answers: update core/knowledge_base.py or add keyword rules below.
"""

import logging

from core.config import OPENAI_API_KEY
from core.knowledge_base import KICKCHAIN_KB
from memory.chat_memory import retrieve_memory_snippets, format_memory_context
from utils.helpers import normalize_text

logger = logging.getLogger(__name__)


def generate_answer(question: str) -> str:
    """
    Main entry point. Priority order:
      1. KB keyword rules — fast, always accurate, no API needed
      2. OpenAI with full KB + memory context
      3. Memory snippets or generic fallback (last resort)
    """
    kb_answer = _answer_kb_keywords(question)
    if kb_answer:
        logger.info("Answered with KB keyword rules.")
        return kb_answer

    memory_snippets = retrieve_memory_snippets(question)
    openai_answer = _answer_openai(question, memory_snippets)
    if openai_answer:
        logger.info("Answered with OpenAI completion.")
        return openai_answer

    logger.warning("Falling back to memory/generic answer for question: %r", question[:120])
    return _answer_memory_or_generic(memory_snippets)


# ─────────────────────────────────────────────
# 1. KB KEYWORD RULES
# ─────────────────────────────────────────────

def _answer_kb_keywords(question: str) -> str | None:
    q = question.lower()

    if any(w in q for w in ["physics", "puck", "drag", "aim", "mechanic", "heavy", "friction", "slide"]):
        return (
            "🎮 *Kickchain Physics Engine:*\n\n"
            "• *Drag-to-aim* — drag to set power and direction, release to strike\n"
            "• *Heavy puck feel* — controlled friction prevents infinite sliding\n"
            "• *Turn-based* — each player takes turns with a strict timer\n"
            "• *Server-authoritative* — server runs ALL physics, clients only render\n"
            "• Zero RNG — pure strategy and precision every shot"
        )

    if any(w in q for w in ["match mode", "game mode", "first to", "timed", "sudden death", "format", "how to play", "how do you play"]):
        return (
            "🏟️ *Kickchain Match Modes:*\n\n"
            "• *First to 3 goals* — classic quick format\n"
            "• *First to 4 goals* — extended competitive format\n"
            "• *Timed (3 min + sudden death)* — next goal wins after time\n\n"
            "All goals confirmed server-side — client pre-scoring disabled."
        )

    if any(w in q for w in ["anomaly", "detection", "anti-cheat", "anticheat", "cheat", "hack", "aimbot", "script", "exploit", "fair"]):
        return (
            "🛡️ *Kickchain Anti-Cheat System:*\n\n"
            "• *Server-authoritative physics* — aimbots completely ineffective\n"
            "• *Strict input validation* — force clamping + turn ownership verified\n"
            "• *Anomaly Detection AI* — monitors impossible accuracy patterns & win-rate anomalies\n"
            "• *Full match replays* — every move stored for audit & dispute resolution\n"
            "• *Auto-flagging* — suspicious wallets frozen instantly"
        )

    if any(w in q for w in ["launch", "release", "when", "ready", "date", "out"]):
        return (
            "📅 *Kickchain V1 Launch: March–April 2026*\n\n"
            "• ✅ Figma Design System — DONE\n"
            "• ✅ Unity Assets — DONE\n"
            "• ✅ Game Economy — DONE\n"
            "• 🔄 Backend Authoritative Structure — IN PROGRESS\n"
            "• 🔄 Multiplayer Validation Logic — IN PROGRESS\n\n"
            "📢 @KickchainChannel | 🎮 https://unique-parfait-7f420d.netlify.app/"
        )

    if any(w in q for w in ["stake", "money", "usdt", "usdc", "real money", "withdraw", "deposit", "wallet"]):
        return (
            "💰 *Real Stakes Mode:*\n\n"
            "Custodial USDT/USDC wallets — winnings *fully withdrawable*\n\n"
            "• Micro: $0.05–$0.20 → 8–10% rake\n"
            "• Low: $0.50–$2.00 → 5–6% rake\n"
            "• Mid: $5–$20 → 3–4% rake\n"
            "• High: $50–$200 → 2–2.5% rake\n"
            "• VIP 👑: $500–$1,000 → 1–1.5% rake\n\n"
            "Withdraw fee: flat $0.25 or 0.5% (max $10)"
        )

    if any(w in q for w in ["referral", "invite", "refer", "earn", "commission"]):
        return (
            "🤝 *Referral Program:*\n\n"
            "🥉 Bronze 10% | 🥈 Silver 15% | 🥇 Gold 20%\n"
            "💎 Platinum 25% | 💠 Diamond 30%\n\n"
            "Eligibility: account ≥ 24hrs + 10 matches played\n\n"
            "👑 *VIP Rakeback:* Silver 2% → Gold 4% → Platinum 6% → Diamond 8%"
        )

    if any(w in q for w in ["revenue", "rake", "profit", "monetiz", "business model", "how does kickchain make"]):
        return (
            "📊 *Revenue Streams:*\n\n"
            "• Match Rake — % of every pot (core)\n"
            "• Withdraw Fee — $0.25 or 0.5% max $10\n"
            "• Tournaments — 10–20% of prize pool\n"
            "• Battle Pass — $4.99 or $9.99/season\n"
            "• Cosmetics Shop — 100% margin digital goods\n"
            "• Rewarded Ads — Fun Mode only\n\n"
            "Pool = Stake×2 → Fee = Pool×Rake% → Winner = Pool - Fee"
        )

    if any(w in q for w in ["tournament", "tournaments", "competition", "event"]):
        return (
            "🏆 *Tournaments:*\n\n"
            "Structured high-prize seasonal events.\n"
            "• Platform takes 10–20% of prize pool\n"
            "• Entry fees apply\n"
            "• Seasonal format with unique prizes & branding"
        )

    if any(w in q for w in ["fun mode", "free", "fun coin", "no money", "without money", "practice"]):
        return (
            "🎮 *Fun Mode* — completely free!\n\n"
            "• Currency: Fun Coins (non-withdrawable)\n"
            "• Earn via: Daily login, Rewarded Ads, Battle Pass\n"
            "• Perfect for onboarding and practice"
        )

    if any(w in q for w in ["battle pass", "season pass", "battlepass"]):
        return (
            "🎫 *Battle Pass:*\n\n"
            "• $4.99 — 14-day season\n"
            "• $9.99 — 30-day season\n"
            "• Exclusive cosmetics, skins, trails & rewards"
        )

    if any(w in q for w in ["retention", "keep playing", "daily", "streak", "leaderboard"]):
        return (
            "🔄 *Retention System:*\n\n"
            "• 🔥 Win Streak Tracking — multipliers for consecutive wins\n"
            "• 📅 Daily Login Rewards — progressive habit formation\n"
            "• 🏆 Leaderboards — global & friends-only rankings\n"
            "• ⚡ Direct Challenges — one-click Telegram challenge links\n"
            "• 🎫 Battle Pass + 🎨 Cosmetic Unlocks"
        )

    if any(w in q for w in ["team", "who made", "developer", "founder", "who built", "who is behind"]):
        return (
            "👥 *The Kickchain Team:*\n\n"
            "• *CORPMEMBER29* — Tech Lead & Architect\n"
            "• *ALI RAZA* — Art Director & Assets\n"
            "• *AHMEDBRO* — Growth & Acquisition"
        )

    if any(w in q for w in ["soccer stars", "inspired", "similar", "difference", "vs"]):
        return (
            "⚽ *Kickchain vs Soccer Stars:*\n\n"
            "Inspired by Soccer Stars' proven mechanic — but taken further:\n"
            "✅ Real money stakes (USDT/USDC)\n"
            "✅ Zero RNG — pure skill\n"
            "✅ Server-authoritative anti-cheat\n"
            "✅ No pay-to-win\n"
            "✅ Telegram-native (900M+ users, no install)"
        )

    if any(w in q for w in ["telegram", "mini app", "tma", "platform", "where to play"]):
        return (
            "📱 *Telegram Mini App (TMA)*\n\n"
            "No install required — play directly inside Telegram.\n"
            "Access to 900M+ users instantly.\n\n"
            "🎮 https://unique-parfait-7f420d.netlify.app/\n"
            "📢 @KickchainChannel"
        )

    if any(w in q for w in ["invest", "opportunity", "why kickchain", "market"]):
        return (
            "💼 *Why Kickchain?*\n\n"
            "• Untapped market — 900M+ Telegram users, no real competitor\n"
            "• Proven mechanic — Soccer Stars formula, millions of daily players\n"
            "• Secure stakes — server-authoritative anti-cheat\n"
            "• Day 1 Revenue — Rake, Fees & Ads from launch\n"
            "• Viral loop — play → invite → earn rake share"
        )

    return None


# ─────────────────────────────────────────────
# 2. OPENAI ANSWERING
# ─────────────────────────────────────────────

def _answer_openai(question: str, memory_snippets: list[dict]) -> str | None:
    if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
        logger.warning("OPENAI_API_KEY missing/empty. Skipping OpenAI answer path.")
        return None

    try:
        from openai import OpenAI
    except Exception:
        logger.exception("Failed to import OpenAI SDK. Falling back.")
        return None

    try:
        memory_context = format_memory_context(memory_snippets)
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the official assistant for Kickchain, a skill-based "
                        "1v1 competitive gaming platform on Telegram.\n"
                        "Rules:\n"
                        "1) Answer using ONLY the evidence provided below.\n"
                        "2) Do not invent facts.\n"
                        "3) If not covered, say: 'I don't have confirmed info on that yet.'\n"
                        "4) Keep answers concise, use bullet points where helpful.\n\n"
                        f"KNOWLEDGE BASE:\n{KICKCHAIN_KB}\n\n"
                        f"COMMUNITY MEMORY:\n{memory_context}"
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=350,
            temperature=0.3,
        )
        content = (resp.choices[0].message.content if resp and resp.choices else None)
        if not content:
            logger.warning("OpenAI returned empty content. Falling back. Question=%r", question[:120])
            return None
        return content.strip()
    except Exception:
        logger.exception("OpenAI request failed. Falling back. Question=%r", question[:120])
        return None


# ─────────────────────────────────────────────
# 3. MEMORY / GENERIC FALLBACK
# ─────────────────────────────────────────────

def _answer_memory_or_generic(memory_snippets: list[dict]) -> str:
    if memory_snippets:
        lines = []
        for s in memory_snippets[:3]:
            user = s.get("user", "unknown")
            ts   = s.get("original_ts") or s.get("ts", "")
            text = normalize_text(s.get("text", ""))[:180]
            lines.append(f"- [{ts}] {user}: {text}")
        return (
            "🧠 Based on saved community chat memory:\n"
            + "\n".join(lines)
            + "\n\nFor official info, check pinned docs or ask the admin."
        )
    return (
        "🤖 I don't have a specific answer for that yet. "
        "Check the pinned message or try /project for a full overview. ⚽"
    )
