# Kickchain Admin Bot

Telegram group bot for the Kickchain project.
Handles Q&A, community signal detection, moderation, announcements, and history backfill.

---

## Project Structure

```text
kickchain_bot/
├── bot.py                   # Entry point: registers handlers and starts polling
├── requirements.txt
├── config/
│   ├── .env
│   └── .env.example
├── core/
│   ├── config.py            # Env parsing and global constants
│   ├── knowledge_base.py    # Kickchain facts for /ask
│   ├── menus.py             # Buttons, keyboards, static reply text
│   └── setup.py             # Telegram command menu registration (post_init)
├── handlers/
│   ├── ask.py               # /ask
│   ├── commands.py          # /start /menu /project /stakes /referral
│   ├── admin.py             # /announce /signalsummary /opinions /memory /scanhistory /testdm
│   ├── moderation.py        # /ban /mute /unmute
│   ├── messages.py          # Group message flow + private ask/announcement input
│   ├── callbacks.py         # Inline callbacks + reply keyboard button handlers
│   └── members.py           # Welcome / leave events
├── services/
│   ├── answering.py         # /ask logic: OpenAI + fallback
│   ├── signals.py           # Signal detection + auto-summary job
│   ├── opinions.py          # Opinions JSONL logging + summary helpers
│   ├── history.py           # Telegram export scanning for /scanhistory
│   └── dm.py                # Admin DM delivery helper
├── memory/
│   └── chat_memory.py       # Memory JSONL write/load/retrieve helpers
└── utils/
    └── helpers.py           # Shared text, flood, permission, and export helpers
```

---

## Runtime Data Paths (Preserved)

The bot keeps using the same data file locations:

- `opinions.jsonl`
- `memory/chat_memory.jsonl`

No data migration is required.

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
cp config/.env.example config/.env
# Edit config/.env with BOT_TOKEN and ADMIN_CHAT_ID

# 3. Run
python bot.py
```

PowerShell helpers are available:

```powershell
./scripts/run_bot.ps1
```

---

## Commands

### User

- `/start`, `/help`
- `/menu`
- `/ask <question>`
- `/project`
- `/stakes`
- `/referral`

### Admin

- `/announce <text>`
- `/signalsummary [hours]`
- `/opinions [n]`
- `/memory [n]`
- `/scanhistory [path] [limit]`
- `/testdm`
- `/ban` (reply)
- `/mute` (reply)
- `/unmute` (reply)

---

## Notes

- Existing `config/.env` variable names are unchanged.
- Entry command remains `python bot.py`.
- `/scanhistory` accepts either JSON export path or Telegram Desktop `messages.html` path.
