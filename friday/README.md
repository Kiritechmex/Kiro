# Friday - Personal AI Assistant

A Telegram bot powered by Google Gemini. Text and voice conversation with memory.

## Features

- **Text chat** with conversation memory (last 20 turns)
- **Voice notes**: send a voice message, get a voice reply (Phase 2)
- Per-user history (commands `/start`, `/reset`, `/help`)
- Customizable owner name and TTS accent

## Quick Start (Termux on Android)

```bash
# 1. Install system dependencies (one time only)
pkg install python git ffmpeg -y
pkg install python-cryptography rust binutils openssl libffi -y

# 2. Clone the repo (one time only)
git clone https://github.com/Kiritechmex/Kiro.git jarvis-bot
cd jarvis-bot/friday

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Create your .env from the template
cp .env.example .env
nano .env
# - Paste your TELEGRAM_BOT_TOKEN
# - Paste your GEMINI_API_KEY
# - Save: Ctrl+X (Volume Down + X), then Y, then Enter

# 5. Run Friday
python bot.py
```

Then open Telegram, find your bot, and send `/start`.

## Commands

- `/start`  Greet Friday and reset the conversation
- `/reset`  Clear conversation memory
- `/help`   Show available commands

## Voice Notes (Phase 2)

Send a voice note to your bot:

1. Friday converts your `.ogg` voice to MP3 (via ffmpeg)
2. Gemini transcribes the audio
3. Gemini generates a reply using your conversation memory
4. gTTS converts the reply to speech
5. ffmpeg converts the speech to `.ogg/Opus` (Telegram voice format)
6. You get a voice note reply

**Customize the voice** by editing `TTS_LANG` and `TTS_TLD` in `.env`. Common options:

- `TTS_LANG=en TTS_TLD=co.in` - Indian English (default)
- `TTS_LANG=en TTS_TLD=us` - American English
- `TTS_LANG=en TTS_TLD=co.uk` - British English
- `TTS_LANG=hi TTS_TLD=co.in` - Hindi

## Stopping the Bot

Press `Ctrl+C` in Termux. (Volume Down + C on phone keyboard.)

## Keep Running After You Close Termux

```bash
termux-wake-lock        # prevents Android from killing Termux
nohup python bot.py &   # runs in background
```

To stop a backgrounded bot: `pkill -f bot.py`

## Updating to the Latest Version

```bash
cd ~/jarvis-bot/friday
git pull
pip install -r requirements.txt
```

## File Layout

- `bot.py`           Main bot code (text + voice)
- `requirements.txt` Python dependencies
- `.env.example`     Template for your secrets
- `.env`             Your real secrets (never committed)

## Phase Roadmap

- [x] Phase 1: Text chat with memory
- [x] Phase 2: Voice notes in/out  <- you are here
- [ ] Phase 3: Tools (weather, web search, reminders)
- [ ] Phase 4: Persistent memory (survives restarts)
- [ ] Phase 5: 24/7 cloud deployment
- [ ] Phase 6: Personality and language tuning

## Troubleshooting

**`ffmpeg: command not found`** -> run `pkg install ffmpeg -y`

**`Voice processing failed: ...`** -> check Termux output. Common: ffmpeg not installed,
or Gemini API rate limit (wait a minute, try again).

**Voice replies sound robotic / wrong accent** -> change `TTS_LANG` and `TTS_TLD` in `.env`.

**Bot does not reply on Telegram** -> verify `python bot.py` is still running.
You should see `HTTP/1.1 200 OK` lines when messages arrive.
