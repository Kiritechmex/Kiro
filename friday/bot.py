"""
Friday - Personal AI Assistant Telegram Bot
Phase 2: Text + Voice conversation with Gemini + per-user memory

Voice flow: voice note -> ffmpeg (ogg/opus -> mp3) -> Gemini transcribes
            -> Gemini replies (with chat memory) -> gTTS -> ffmpeg (mp3 -> ogg/opus)
            -> Telegram voice reply

Run with:  python bot.py
"""

import io
import logging
import os
import subprocess

from dotenv import load_dotenv
from google import genai
from google.genai import types
from gtts import gTTS
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Load configuration from .env
# ---------------------------------------------------------------------------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_NAME = os.getenv("OWNER_NAME", "Sir")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TTS_LANG = os.getenv("TTS_LANG", "en")
TTS_TLD = os.getenv("TTS_TLD", "co.in")  # Indian English accent by default
MAX_HISTORY_TURNS = 20

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError(
        "Missing TELEGRAM_BOT_TOKEN or GEMINI_API_KEY. "
        "Copy .env.example to .env and fill in your real keys."
    )

# ---------------------------------------------------------------------------
# Configure Gemini client + Friday's personality
# ---------------------------------------------------------------------------
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = f"""You are Friday, a personal AI assistant for {OWNER_NAME}.

Personality:
- Warm, witty, efficient, and concise.
- Speak like a trusted assistant: professional but friendly.
- Keep replies short for casual chat, detailed when {OWNER_NAME} asks for help.
- If you do not know something, say so honestly. Never invent facts.
- For voice replies, keep your answer short and conversational so it sounds
  natural when read aloud. Avoid markdown, code blocks, and bullet lists.

You can answer questions, help with tasks, brainstorm ideas, or just chat.
"""

GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
)

# Per-user conversation history. Resets if the bot is restarted.
user_histories: dict[int, list] = {}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("friday")


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------
def get_history(user_id: int) -> list:
    """Return mutable conversation history for this user."""
    if user_id not in user_histories:
        user_histories[user_id] = []
    return user_histories[user_id]


def trim_history(history: list, max_turns: int = MAX_HISTORY_TURNS) -> None:
    """Keep history bounded so we do not blow past token limits."""
    max_messages = max_turns * 2
    if len(history) > max_messages:
        del history[: len(history) - max_messages]


# ---------------------------------------------------------------------------
# Audio helpers (ffmpeg via subprocess - no pydub/audioop needed on Py 3.13)
# ---------------------------------------------------------------------------
def _ffmpeg(input_bytes: bytes, *args: str) -> bytes:
    """Run ffmpeg with given args, piping input/output via stdin/stdout."""
    cmd = ["ffmpeg", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(
        cmd,
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed: {proc.stderr.decode('utf-8', errors='ignore')}"
        )
    return proc.stdout


def ogg_to_mp3(ogg_bytes: bytes) -> bytes:
    """Convert Telegram's OGG/Opus voice note to MP3 (Gemini-friendly)."""
    return _ffmpeg(
        ogg_bytes,
        "-i", "pipe:0",
        "-f", "mp3",
        "pipe:1",
    )


def text_to_voice_ogg(text: str) -> bytes:
    """Convert text to OGG/Opus bytes for a Telegram voice note."""
    # Step 1: gTTS produces MP3 audio
    mp3_buf = io.BytesIO()
    gTTS(text=text, lang=TTS_LANG, tld=TTS_TLD).write_to_fp(mp3_buf)
    mp3_bytes = mp3_buf.getvalue()

    # Step 2: ffmpeg converts MP3 -> OGG/Opus (Telegram voice format)
    return _ffmpeg(
        mp3_bytes,
        "-i", "pipe:0",
        "-c:a", "libopus",
        "-b:a", "32k",
        "-f", "ogg",
        "pipe:1",
    )


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/mp3") -> str:
    """Transcribe a short audio clip using Gemini."""
    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            "Transcribe this voice message verbatim. "
            "Return ONLY the transcription text, nothing else.",
            audio_part,
        ],
    )
    return (response.text or "").strip()


# ---------------------------------------------------------------------------
# Telegram command handlers
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories.pop(update.effective_user.id, None)
    await update.message.reply_text(
        f"Hello {OWNER_NAME}. Friday online. "
        "Send me text or a voice note - I'll reply in the same format."
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_histories.pop(update.effective_user.id, None)
    await update.message.reply_text("Memory cleared. Starting fresh.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start  - Greet Friday and reset session\n"
        "/reset  - Clear conversation memory\n"
        "/help   - Show this help\n\n"
        "Send text - get text reply.\n"
        "Send a voice note - get a voice reply.\n"
        "Friday remembers the last 20 turns of conversation."
    )


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply to a plain text message."""
    user_id = update.effective_user.id
    user_text = update.message.text or ""

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    history = get_history(user_id)
    history.append({"role": "user", "parts": [{"text": user_text}]})

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=history,
            config=GENERATION_CONFIG,
        )
        reply_text = (response.text or "").strip() or "I am not sure how to respond to that."
        history.append({"role": "model", "parts": [{"text": reply_text}]})
        trim_history(history)
    except Exception as exc:  # noqa: BLE001
        log.exception("Gemini text request failed")
        if history and history[-1].get("role") == "user":
            history.pop()
        reply_text = f"Sorry, something went wrong: {exc}"

    await update.message.reply_text(reply_text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply to a voice note: transcribe -> ask Gemini -> speak back."""
    user_id = update.effective_user.id
    voice = update.message.voice
    if not voice:
        return

    chat_id = update.effective_chat.id
    history = get_history(user_id)

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")

        # Download voice from Telegram (.ogg/Opus)
        voice_file = await voice.get_file()
        ogg_bytes = bytes(await voice_file.download_as_bytearray())

        # Convert to MP3 for Gemini
        mp3_bytes = ogg_to_mp3(ogg_bytes)

        # Transcribe via Gemini
        transcription = await transcribe_audio(mp3_bytes, mime_type="audio/mp3")
        if not transcription:
            await update.message.reply_text(
                "Sorry, I could not understand the voice message. Please try again."
            )
            return
        log.info("Voice transcribed: %s", transcription[:120])

        # Add to conversation, get reply
        history.append({"role": "user", "parts": [{"text": transcription}]})
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=history,
            config=GENERATION_CONFIG,
        )
        reply_text = (response.text or "").strip() or "I am not sure how to respond to that."
        history.append({"role": "model", "parts": [{"text": reply_text}]})
        trim_history(history)

        # Generate TTS voice reply
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        voice_bytes = text_to_voice_ogg(reply_text)

        await update.message.reply_voice(voice=voice_bytes)
    except Exception as exc:  # noqa: BLE001
        log.exception("Voice handling failed")
        if history and history[-1].get("role") == "user":
            history.pop()
        await update.message.reply_text(f"Sorry, voice processing failed: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    log.info("Starting Friday with model=%s", GEMINI_MODEL)
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    log.info("Friday is polling for messages. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
