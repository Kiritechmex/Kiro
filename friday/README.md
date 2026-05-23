# Friday - Personal AI Assistant (Phase 1)

A Telegram bot powered by Google Gemini. Phase 1 is text-only with conversation memory.

## Quick Start (Termux on Android)

```bash
# 1. Clone the repo (only needed once)
git clone https://github.com/Kiritechmex/Kiro.git
cd Kiro/friday

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env from the template
cp .env.example .env
nano .env
# - Paste your TELEGRAM_BOT_TOKEN
# - Paste your GEMINI_API_KEY
# - Save: Ctrl+X, then Y, then Enter
#   (in Termux, "Ctrl" = hold Volume Down)

# 4. Run Friday
python bot.py
```

Then open Telegram, find your bot, and send `/start`.

## Commands

- `/start`  Greet Friday and reset the conversation
- `/reset`  Clear conversation memory
- `/help`   Show available commands

Any other message is sent to Gemini for a reply.

## Files

- `bot.py`           Main bot code
- `requirements.txt` Python dependencies
- `.env.example`     Template for your secrets
- `.env`             Your real secrets (never committed)

## Stopping the bot

Press `Ctrl+C` in Termux. (Volume Down + C on phone keyboard.)

## Keep running after you close Termux

```bash
termux-wake-lock        # prevents Android from killing Termux
nohup python bot.py &   # runs in background
```

To stop a backgrounded bot: `pkill -f bot.py`

## Phase Roadmap

- [x] Phase 1: Text chat with memory  <- you are here
- [ ] Phase 2: Voice notes in/out
- [ ] Phase 3: Tools (weather, web search, reminders)
- [ ] Phase 4: Persistent memory
- [ ] Phase 5: 24/7 cloud deployment
