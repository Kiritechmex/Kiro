"""
Friday - Personal AI Assistant Telegram Bot
Phase 1: Text conversation with Gemini + per-user memory

Uses the new google-genai SDK (HTTP-based, no grpcio needed).
Run with:  python bot.py
"""

import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
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
MAX_HISTORY_TURNS = 20  # keep last 20 user/model exchanges

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
# Helpers
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
# Telegram command handlers
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greet the user and start a fresh session."""
    user_histories.pop(update.effective_user.id, None)
    await update.message.reply_text(
        f"Hello {OWNER_NAME}. Friday online. What can I do for you?"
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear conversation memory for this user."""
    user_histories.pop(update.effective_user.id, None)
    await update.message.reply_text("Memory cleared. Starting fresh.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available commands."""
    await update.message.reply_text(
        "Commands:\n"
        "/start  - Greet Friday and reset session\n"
        "/reset  - Clear conversation memory\n"
        "/help   - Show this help\n\n"
        "Or just send any message and I will reply."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages by sending them to Gemini."""
    user_id = update.effective_user.id
    user_text = update.message.text or ""

    # Show "typing..." indicator while Gemini thinks
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
    except Exception as exc:  # noqa: BLE001 - surface any error to the user
        log.exception("Gemini request failed")
        # Roll back the user message we appended so retry works clean
        if history and history[-1].get("role") == "user":
            history.pop()
        reply_text = f"Sorry, something went wrong: {exc}"

    await update.message.reply_text(reply_text)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    log.info("Starting Friday with model=%s", GEMINI_MODEL)
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Friday is polling for messages. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
