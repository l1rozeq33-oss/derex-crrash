import os
import asyncio
import threading

from fastapi import FastAPI
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://derex-crrash.onrender.com")

# ================== FASTAPI ==================
app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok", "service": "DerexCrash"}


# ================== TELEGRAM LOGIC ==================
def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🚀 Играть в Crash",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="profile")
        ]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎰 *DerexCasino*\n\n"
        "Добро пожаловать!\n"
        "Нажми кнопку ниже и начни игру 🚀",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "profile":
        await query.edit_message_text(
            "👤 *Профиль*\n\n"
            "Баланс: 0$\n"
            "Игр: 0\n"
            "Побед: 0",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Используй кнопки 👇", reply_markup=main_menu())


# ================== BOT START ==================
async def start_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN not set")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callbacks))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Telegram bot started (polling)")
    await application.run_polling()


# ================== RUN BOT ON STARTUP ==================
@app.on_event("startup")
def startup_event():
    threading.Thread(
        target=lambda: asyncio.run(start_bot()),
        daemon=True
    ).start()
