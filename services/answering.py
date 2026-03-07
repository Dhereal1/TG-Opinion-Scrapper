"""
services/answering.py
=====================
Question answering for the /ask command.
"""

import logging

from core.config import OPENAI_API_KEY
from core.knowledge_base import KICKCHAIN_KB
from memory.chat_memory import retrieve_memory_snippets, format_memory_context
from utils.helpers import normalize_text

logger = logging.getLogger(__name__)



def generate_answer(question: str) -> str:
    """Main entry point: generate the best available answer for a question."""
    memory_snippets = retrieve_memory_snippets(question)
    return _answer_openai(question, memory_snippets) or _answer_keyword_fallback(question, memory_snippets)



def _answer_openai(question: str, memory_snippets: list[dict]) -> str | None:
    """Use OpenAI GPT-4o-mini grounded on KB + memory snippets."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

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
                        "3) If evidence is missing or uncertain, say clearly: "
                        "'I don't have enough confirmed info from saved docs/chat memory yet.'\n"
                        "4) Keep answers concise and practical.\n\n"
                        f"KNOWLEDGE BASE:\n{KICKCHAIN_KB}\n\n"
                        f"COMMUNITY MEMORY SNIPPETS:\n{memory_context}"
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=300,
            temperature=0.4,
        )
        content = resp.choices[0].message.content
        return content.strip() if content else None
    except Exception as e:
        logger.error("OpenAI error: %s", e)
        return None



def _answer_keyword_fallback(question: str, memory_snippets: list[dict]) -> str:
    """
    Keep existing production fallback behavior:
    memory-first, then keyword-based KB rules.
    """
    if memory_snippets:
        lines = []
        for s in memory_snippets[:3]:
            user = s.get("user", "unknown")
            ts = s.get("original_ts") or s.get("ts", "")
            text = normalize_text(s.get("text", ""))[:180]
            lines.append(f"- [{ts}] {user}: {text}")
        return (
            "🧠 Based on saved community chat memory, here are the most relevant messages:\n"
            + "\n".join(lines)
            + "\n\nIf you need official confirmation, check pinned docs or ask the admin."
        )

    q = question.lower()

    if any(w in q for w in ["launch", "release", "when", "ready"]):
        return (
            "🚀 Kickchain V1 is targeting a *March-April 2026* launch. "
            "Stay tuned in the channel @kickchainchannel!\n"
            "🎮 Play now: https://unique-parfait-7f420d.netlify.app/"
        )
    if any(w in q for w in ["stake", "money", "usdt", "usdc", "real money", "withdraw"]):
        return (
            "💰 Kickchain's *Real Stakes* mode uses custodial USDT/USDC wallets. "
            "Winnings are fully withdrawable. Stake tiers range from *Micro ($0.05)* to *VIP ($1,000)*. "
            "A small rake fee is taken per match."
        )
    if any(w in q for w in ["hack", "cheat", "aimbot", "script"]):
        return (
            "🛡️ Kickchain uses a *server-authoritative engine*. "
            "The server runs all physics - clients only send input vectors. "
            "Aimbots and client-side scripts are completely ineffective here!"
        )
    if any(w in q for w in ["referral", "invite", "earn"]):
        return (
            "🤝 The *Referral System* lets you earn a share of your referrals' rake fees: "
            "Bronze 10% -> Diamond 30%. Invite friends and earn passively!"
        )
    if any(w in q for w in ["tournament", "tournaments"]):
        return (
            "🏆 *Tournaments* are structured high-prize events. "
            "The platform reserves 10-20% of the prize pool. Entry fees apply."
        )
    if any(w in q for w in ["free", "fun mode", "no money", "without money"]):
        return (
            "🎮 *Fun Mode* is completely free! You play with Fun Coins (non-withdrawable) "
            "and earn rewards via daily login, ads, and the Battle Pass."
        )
    if any(w in q for w in ["battle pass", "season"]):
        return "🎫 *Battle Pass* costs $4.99 (14 days) or $9.99 (30 days) per season and unlocks exclusive cosmetics & rewards."
    if any(w in q for w in ["team", "who made", "developer", "founder"]):
        return (
            "👥 *The Kickchain Team:*\n"
            "• CORPMEMBER29 - Tech Lead & Architect\n"
            "• ALI RAZA - Art Director & Assets\n"
            "• AHMEDBRO - Growth & Acquisition"
        )

    return (
        "🤖 Good question! I don't have a specific answer for that. "
        "Feel free to ping the admin directly or check the pinned message for the full whitepaper. "
        "You can also ask in the group - the team reads everything! ⚽"
    )
