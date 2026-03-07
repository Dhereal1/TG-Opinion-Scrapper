"""
core/knowledge_base.py
======================
Kickchain project knowledge base used by the /ask command.
Update this file whenever the project details change.
"""

KICKCHAIN_KB = """
Kickchain is a skill-based 1v1 competitive gaming platform built natively on Telegram (Telegram Mini App).

CORE CONCEPT:
- Physics-based soccer / puck game inspired by Soccer Stars
- Turn-based system: players take turns shooting with a drag-to-aim mechanic
- No RNG - pure strategy and precision
- Server-authoritative engine: all physics (collisions, friction, goals) computed server-side; client only renders
- Anti-cheat: input validation, anomaly AI, full match replays stored

GAME MODES:
- Fun Mode: off-chain economy with Fun Coins (non-withdrawable). Monetized via ads, in-app purchases, Battle Pass, cosmetics
- Real Stakes Mode: custodial USDT/USDC wallets. Fully withdrawable winnings. Match rake fee taken from pot.

STAKE TIERS (Real Stakes):
- Micro: $0.05-$0.20 -> 8-10% rake
- Low: $0.50-$2.00 -> 5-6% rake
- Mid: $5-$20 -> 3-4% rake
- High: $50-$200 -> 2-2.5% rake
- VIP: $500-$1,000 -> 1-1.5% rake

REVENUE STREAMS:
- Match Rake (core) - percentage of every pot
- Withdraw fee: flat $0.25 or 0.5% (max $10)
- Tournaments: 10-20% of prize pool
- Battle Pass: $4.99 or $9.99/season (14 or 30 days)
- Cosmetics Shop (puck skins, trails, goal explosions) - 100% margin
- Rewarded Ads (Fun Mode only)

REFERRAL SYSTEM (revenue share for referring users):
- Bronze 10% / Silver 15% / Gold 20% / Platinum 25% / Diamond 30%

VIP RAKEBACK:
- Bronze 0% / Silver 2% / Gold 4% / Platinum 6% / Diamond 8%

TECH STACK:
- Platform: Telegram Mini App (TMA)
- Frontend: Mobile-first adaptive UI (Figma complete)
- Backend: Server-authoritative Node.js engine
- Blockchain: Custodial USDT/USDC wallets

DEVELOPMENT STATUS (as of early 2026):
- Figma Design System: DONE
- Unity Assets in Production: DONE
- Game Economy Fully Designed: DONE
- Backend Authoritative Structure: IN PROGRESS
- Multiplayer Validation Logic: IN PROGRESS
- Target V1 launch: March-April 2026

TEAM:
- CORPMEMBER29 - Tech Lead & Architect (Frontend, Backend, Blockchain)
- ALI RAZA - Art Director & Assets (Unity, Game Art, UX)
- AHMEDBRO - Growth & Acquisition (UA, Community, Marketing)

GO-TO-MARKET:
- 100,000 DM campaign targeting Soccer Stars communities (Telegram, Discord, Reddit, Instagram, Facebook)
- Viral loop: user plays -> invites friends -> friends play -> user earns rake share
"""
