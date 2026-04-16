import logging
import asyncio
import os
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from agent import run_agent

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# In-memory store: { user_id: [BaseMessage, ...] }
user_histories: dict[int, list] = {}

GREETING = (
    "👋 Hello! I'm your AI Calendar Manager.\n\n"
    "Try: 'What do I have this week?' or 'Schedule a meeting tomorrow at 2pm'\n\n"
    "Send /clear to reset conversation history."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []  # reset on /start
    await update.message.reply_text(GREETING, parse_mode="HTML")


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("🗑️ Conversation history cleared!")


def markdown_to_html(text: str) -> str:
    """Convert any leftover **bold** or *italic* markdown to HTML tags."""
    # Convert **bold** → <b>bold</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Convert *italic* or _italic_ → <i>italic</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'_(.+?)_', r'<i>\1</i>', text)
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    if not user_text:
        return

    if user_id not in user_histories:
        user_histories[user_id] = []

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        reply, updated_history = await run_agent(user_text, user_histories[user_id])
        user_histories[user_id] = updated_history

        if reply:
            for chunk in split_message(reply):
                await update.message.reply_text(markdown_to_html(chunk), parse_mode="HTML")
        else:
            await update.message.reply_text("⚙️ Done! Let me know if you need anything else.")

    except Exception as e:
        logging.error(f"Agent error for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Something went wrong. Please try again or send /clear to reset."
            
        )


def split_message(text: str, limit: int = 4096) -> list[str]:
    """Split long messages to respect Telegram's character limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())  # ← add this line

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running... Press Ctrl+C to stop.")
    app.run_polling()