# Kickchain Admin Bot 🤖⚽

A Telegram bot for the **Kickchain** community group that acts as:
- **Group Moderator** — welcomes members, mutes flooders, ban/mute tools for admin
- **Chat Assistant** — answers questions via `/ask` using KB + saved chat memory
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
| `UI Buttons` | Tap Ask / Project / Stakes / Referral inline buttons (or use `/menu`) |
| `/ask <question>` | Grounded answers using Kickchain KB + remembered chat history |
| `/project` | Quick project summary |
| `/stakes` | Stake tiers & rake fee table |
| `/referral` | Referral program & VIP rakeback details |

### 💡 Opinion / Idea Extraction
The bot **silently monitors all messages** and automatically detects:
- Suggestions ("I think", "it would be great if", "what if")
- Feature requests ("can you add", "please add", "would love")
- Feedback & bugs ("issue", "problem", "not working")
- Gameplay opinions (physics, balance, matchmaking, tournaments...)

When a qualifying message is found, configured admin(s) instantly receive a private message like:

```
💡 New Opinion / Idea Detected
👤 From: Thameem_Kopa

"You're not gonna believe how huge the soccer stars community is"

🔗 View in group
```

All opinions are also saved to `opinions.jsonl` locally.
All normal group messages are also saved in `memory/chat_memory.jsonl` for retrieval.

For older messages, use `/scanhistory` to backfill memory + opinions from Telegram export history.

### 📋 Admin Commands
| Command | Description |
|---|---|
| `/announce <text>` | Admin: send announcement to configured channels |
| `/opinions [n]` | Show last N collected opinions (default: 10) |
| `/memory [n]` | Show last N remembered chat messages (admin only) |
| `/scanhistory [path] [limit]` | Backfill memory + opinions from Telegram exported history |
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
- **Second admin ID (optional):** Repeat for your second admin account
- **Group ID:** Forward any group message to `@userinfobot` → copy "Forwarded from chat Id" (starts with `-100`)

### 3. Configure environment
```bash
cp config/.env.example config/.env
# Edit config/.env with your BOT_TOKEN, ADMIN_CHAT_ID, GROUP_ID
# Optional: SECOND_ADMIN_CHAT_ID (or ADMIN_CHAT_IDS comma-separated)
# Optional: ANNOUNCEMENT_CHANNEL_IDS for /announce
```

### 4. Install & run
```bash
# PowerShell:
./scripts/run_bot.ps1

# OR activate only:
./scripts/activate_venv.ps1
# Bash/WSL:
source ./scripts/activate_venv.sh

# Run the bot
python bot.py
```
If PowerShell blocks script execution, run once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 5. (Optional) Enable smarter /ask with OpenAI
Add your OpenAI API key to `config/.env`:
```
OPENAI_API_KEY=sk-...
```
Without it, the bot uses a built-in keyword-based Q&A system covering all Kickchain topics.

### 6. (Optional) Backfill memory + opinions from history
Telegram bots cannot fetch full old chat history directly via Bot API.  
To process older messages:

1. Export group history from Telegram Desktop as JSON.
2. Save the file as `config/group_history_export.json` (or any path).
3. Run bot, then execute in Telegram (as admin):

```text
/scanhistory
```

Or with custom path/limit:
```text
/scanhistory config/group_history_export.json 5000
```

You can also pass Telegram Desktop HTML export path directly; the bot auto-uses sibling `result.json`:
```text
/scanhistory C:/Users/USER/Downloads/Telegram Desktop/ChatExport_2026-03-01/messages.html
```

### 7. (Optional) Channel announcements
Set announcement targets in `config/.env`:
```env
ANNOUNCEMENT_CHANNEL_IDS=-1001234567890,@yourchannel
```
Then send (admin only):
```text
/announce Your announcement text here
```

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
├── scripts/
│   ├── activate_venv.ps1  # Auto-create/activate venv on PowerShell
│   ├── activate_venv.sh   # Auto-create/activate venv on bash/WSL
│   └── run_bot.ps1        # Activate venv + run bot in one command
├── config/
│   ├── .env.example  # Environment template
│   ├── .env          # Your actual secrets (never commit this!)
│   └── group_history_export.json  # Optional Telegram export for /scanhistory
├── memory/
│   └── chat_memory.jsonl  # Auto-created persistent message memory
└── opinions.jsonl    # Auto-created: log of all detected opinions
```
# TG-Opinion-Scrapper
