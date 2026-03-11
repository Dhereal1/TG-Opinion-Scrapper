"""
core/knowledge_base.py
======================
Kickchain project knowledge base used by the /ask command.
Update this file whenever the project details change.
"""

KICKCHAIN_KB = """
Kickchain is a skill-based 1v1 competitive gaming platform built natively on Telegram (Telegram Mini App).
Tagline: "Where Skill Meets Stakes"

═══════════════════════════════════════
THE PROBLEM KICKCHAIN SOLVES
═══════════════════════════════════════
- Luck Dominance: Telegram gaming is saturated with click-farm and luck-based games offering zero depth for serious players.
- No Real Stakes: Virtually no skill-based competitive options let players wager real value on their performance.
- Unmonetized Skill: Highly skilled mobile gamers have no direct path to monetize their talent without becoming professional esports athletes.
- Pay-to-Win Fatigue: Existing "competitive" titles are often predatory pay-to-win schemes or centralized black boxes with no transparency.

═══════════════════════════════════════
CORE CONCEPT
═══════════════════════════════════════
- Physics-based soccer / puck game inspired by Soccer Stars (the proven mechanic with millions of daily active players)
- Turn-based system: players take turns shooting with a drag-to-aim mechanic
- No RNG — pure strategy and precision
- Server-authoritative engine: all physics (collisions, friction, goals) computed server-side; client only renders
- No Pay-to-Win: purchases are strictly cosmetic or for entry fees, never for gameplay advantages

═══════════════════════════════════════
HOW IT WORKS — GAMEPLAY MECHANICS
═══════════════════════════════════════
1. DRAG-TO-AIM: Intuitive shooting mechanic where players drag to set power and direction, then release to strike the puck.
2. TURN-BASED SYSTEM: Strategic gameplay where each player takes turns shooting. A strict timer ensures fast-paced matches.
3. HEAVY PHYSICS: Engineered for a "heavy puck feel" with controlled friction, preventing infinite sliding and ensuring skill mastery.
4. SERVER VALIDATION: Server-authoritative engine validates every input vector. The client only renders what the server confirms.
5. MATCH MODES: Flexible competitive formats — First to 3 goals, First to 4 goals, or Timed (3 min + sudden death).
6. SECURE SCORING: Goals are confirmed server-side only. Client pre-scoring is disabled to prevent state manipulation hacks.

═══════════════════════════════════════
TWO PARALLEL ECONOMIES
═══════════════════════════════════════
FUN MODE (Off-Chain Economy):
- Currency: Fun Coins (non-withdrawable)
- Purpose: Onboarding funnel, retention, viral growth
- Monetization: Rewarded Ads, In-App Purchases, Battle Pass, Cosmetics

REAL STAKES MODE (Custodial Stablecoins):
- Currency: USDT + USDC (fully withdrawable)
- Purpose: Competitive play, high LTV users, core revenue
- Monetization: Match Rake, Withdraw Fee, Tournaments, Premium Cosmetics

═══════════════════════════════════════
STAKE TIER SYSTEM
═══════════════════════════════════════
- Micro: $0.05 / $0.10 / $0.20 → 8–10% rake
- Low:   $0.50 / $1.00 / $2.00 → 5–6% rake
- Mid:   $5.00 / $10.00 / $20.00 → 3–4% rake
- High:  $50 / $100 / $200 → 2–2.5% rake
- VIP:   $500 / $1,000 → 1–1.5% rake

Progressive Rake Model: Higher rake on micro stakes ensures profitability on high-volume casual play, while ultra-low fees on high stakes attract and retain "whales" (high-volume players).

Core Loop: Pool = Stake × 2 → Fee = Pool × Rake% → Winner = Pool - Fee

═══════════════════════════════════════
REVENUE STREAMS
═══════════════════════════════════════
- Match Rake (CORE): Percentage of every match pot. Primary revenue driver scaling with volume.
- Withdraw Fee: Flat $0.25 or 0.5% (max $10) to cover operational costs on cashouts.
- Tournaments: Entry fees for high-prize structured events. 10–20% of prize pool reserved for platform.
- Battle Pass: Seasonal recurring revenue. $4.99 or $9.99 per season (14 or 30 days).
- Cosmetics Shop: Vanity items — puck skins, trails, goal explosions. 100% margin digital goods.
- Rewarded Ads: Fun Mode only. Monetizes non-paying users. High fill rate for game currency.

═══════════════════════════════════════
REFERRAL & VIP PROGRAM
═══════════════════════════════════════
REFERRAL SYSTEM (Revenue Share):
- Bronze: 10% share
- Silver: 15% share
- Gold (Default): 20% share
- Platinum: 25% share
- Diamond: 30% share

Anti-Fraud Eligibility Rules:
- Account age ≥ 24 hours
- Played ≥ 10 matches total

VIP RAKEBACK (Volume-Based Retention):
- Bronze: 0% rakeback
- Silver: 2% rakeback
- Gold: 4% rakeback
- Platinum: 6% rakeback
- Diamond: 8% rakeback

═══════════════════════════════════════
ANTI-CHEAT & INTEGRITY SYSTEM
═══════════════════════════════════════
- Server-Authoritative Physics: Client sends input vectors only. The server runs the actual simulation, making aimbots completely ineffective.
- Server-Side Computation: All collisions, friction, bounces, and goal events are calculated strictly on the backend.
- Strict Input Validation: Server enforces force clamping limits and verifies turn ownership before accepting any move.
- Full Match Replays: Every move is stored in the match_moves database table for automated audit and dispute resolution.
- Anomaly Detection AI: Monitors for impossible accuracy patterns, repeated shot vectors, and statistical win-rate anomalies.
- Reporting & Flagging: User reporting tools integrated with an automatic flagging system to freeze suspicious wallets instantly.

═══════════════════════════════════════
RETENTION ARCHITECTURE
═══════════════════════════════════════
- Win Streak Tracking: Visual indicators and multipliers for consecutive wins to encourage "one more game".
- Daily Login Rewards: Progressive rewards for returning daily, building habit formation.
- Battle Pass: Seasonal progression system unlocking exclusive cosmetics and rewards.
- Leaderboards: Global and friends-only rankings to drive competitive social pressure.
- Direct Challenges: One-click Telegram links to challenge friends directly in chat.
- Cosmetic Unlocks: Deep personalization for pucks and trails to express player identity.
- Tournament Events: Seasonal high-stakes tournaments with unique prizes and branding.

═══════════════════════════════════════
TECH STACK
═══════════════════════════════════════
- Platform: Telegram Mini App (TMA)
- Frontend: Mobile-first adaptive UI (Figma complete)
- Backend: Server-Authoritative Node.js Engine
- Blockchain: Custodial USDT/USDC Wallets

═══════════════════════════════════════
DEVELOPMENT STATUS (as of early 2026)
═══════════════════════════════════════
- Figma Design System: ✅ DONE
- Unity Assets in Production: ✅ DONE
- Game Economy Fully Designed: ✅ DONE
- Backend Authoritative Structure: 🔄 IN PROGRESS
- Multiplayer Validation Logic: 🔄 IN PROGRESS
- Target V1 Launch: March–April 2026

═══════════════════════════════════════
TEAM
═══════════════════════════════════════
- CORPMEMBER29 — Tech Lead & Architect (Frontend & TMA Integration, Server-Authoritative Backend, Blockchain & Wallet Systems)
- ALI RAZA — Art Director & Assets (Unity Physics-Ready Assets, Game Art Production, Visual Experience & UX)
- AHMEDBRO — Growth & Acquisition (User Acquisition Strategy, Community Management, Marketing & Partnerships)

═══════════════════════════════════════
GO-TO-MARKET STRATEGY
═══════════════════════════════════════
- Mass DM Campaign: 100,000 DMs targeting Soccer Stars communities on Telegram, Discord, Reddit, Instagram, Facebook
- Message Strategy: High-curiosity hook + Skill-based positioning + Instant Play link
- Unique referral tracking link for every user
- Viral Loop: User plays → Invites friends → Friends play → User earns rake share (self-feeding growth)

═══════════════════════════════════════
INVESTMENT HIGHLIGHTS
═══════════════════════════════════════
- Untapped Market: Direct access to 900M+ Telegram users with no app install friction
- Proven Mechanic: Soccer Stars formula already validates millions of daily active players
- Secure Stakes: Real-money competition protected by server-authoritative anti-cheat
- Day 1 Revenue: Multiple monetization streams live from launch — Rake, Fees & Ads

Channel: @KickchainChannel
Play now: https://unique-parfait-7f420d.netlify.app/
"""
