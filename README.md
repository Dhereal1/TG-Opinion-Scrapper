# Kickchain Admin Bot 🤖⚽

A Telegram bot for the **Kickchain** community group that acts as:
- **Group Moderator** — welcomes members, mutes flooders, ban/mute tools for admin
- **Chat Assistant** — answers questions about Kickchain via `/ask`
- **Opinion Extractor** — silently detects and forwards community opinions/ideas to you in private chat

---

## Features

### 🛡️ Moderation
| Feature | Details |
|---|---|
| Welcome message | Auto-sent to every new member with project summary & commands |
| Anti-flood | Mutes users who send >5 messages in 10 seconds |
| `/ban` | Admin: reply to a message → ban that user |
| `/mute` | Admin: reply to a message → mute for 1 hour |
| `/unmute` | Admin: reply to a message → unmute |

### 🤖 Chat Assistant (for group members)
| Command | Description |
|---|---|
| `/ask <question>` | AI-powered answers about Kickchain (uses OpenAI if key provided, falls back to built-in KB) |
| `/project` | Quick project summary |
| `/stakes` | Stake tiers & rake fee table |
| `/referral` | Referral program & VIP rakeback details |

### 💡 Opinion / Idea Extraction
The bot **silently monitors all messages** and automatically detects:
- Suggestions ("I think", "it would be great if", "what if")
- Feature requests ("can you add", "please add", "would love")
- Feedback & bugs ("issue", "problem", "not working")
- Gameplay opinions (physics, balance, matchmaking, tournaments...)

When a qualifying message is found, you instantly receive a private message like:

```
💡 New Opinion / Idea Detected
👤 From: Thameem_Kopa

"You're not gonna believe how huge the soccer stars community is"

🔗 View in group
```

All opinions are also saved to `opinions.jsonl` locally.

### 📋 Admin Commands
| Command | Description |
|---|---|
| `/opinions [n]` | Show last N collected opinions (default: 10) |
| `/ban` | Ban user (reply to their message) |
| `/mute` | Mute user 1hr (reply to their message) |
| `/unmute` | Unmute user (reply to their message) |

---

## Setup

### 1. Create the bot
1. Message **@BotFather** on Telegram
2. `/newbot` → follow instructions → copy the **token**
3. Add the bot to your Kickchain group as an **Admin** with these permissions:
   - Delete messages
   - Ban users
   - Restrict members

### 2. Get your IDs
- **Your admin ID:** Message `@userinfobot` → copy "Id"
- **Group ID:** Forward any group message to `@userinfobot` → copy "Forwarded from chat Id" (starts with `-100`)

### 3. Configure environment
```bash
cp config/.env.example config/.env
# Edit config/.env with your BOT_TOKEN, ADMIN_CHAT_ID, GROUP_ID
```

### 4. Install & run
```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

### 5. (Optional) Enable smarter /ask with OpenAI
Add your OpenAI API key to `config/.env`:
```
OPENAI_API_KEY=sk-...
```
Without it, the bot uses a built-in keyword-based Q&A system covering all Kickchain topics.

---

## Deploying 24/7

For continuous operation, deploy on a cheap VPS (e.g. DigitalOcean $4/mo, Railway, Render):

```bash
# Using screen (simplest)
screen -S kickchain-bot
python bot.py
# Ctrl+A, D to detach

# OR using systemd service (recommended for production)
# Create /etc/systemd/system/kickchain-bot.service
```

**systemd service example:**
```ini
[Unit]
Description=Kickchain Telegram Bot
After=network.target

[Service]
WorkingDirectory=/path/to/kickchain_bot
ExecStart=/path/to/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Opinion Detection Logic

The bot flags messages containing patterns like:
- `should`, `could`, `would be great/nice/cool`
- `i think`, `in my opinion`, `imo`, `imho`
- `suggestion`, `idea`, `feature`, `please add`
- `problem`, `issue`, `bug`, `fix`, `broken`
- `what if`, `how about`, `why not`, `would love`
- Physics, balance, tournament, leaderboard, matchmaking references

Messages shorter than 20 characters are ignored.

---

## File Structure
```
kickchain_bot/
├── bot.py            # Main bot code
├── requirements.txt  # Python dependencies
├── config/
│   ├── .env.example  # Environment template
│   └── .env          # Your actual secrets (never commit this!)
└── opinions.jsonl    # Auto-created: log of all detected opinions
```
# TG-Opinion-Scrapper
