import os
import logging
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = WEBAPP_URL + WEBHOOK_PATH

logging.basicConfig(level=logging.INFO)

# ================== FASTAPI ==================
app = FastAPI()

# ================== TELEGRAM ==================
tg_app = Application.builder().token(BOT_TOKEN).build()

# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🚀 Играть", web_app={"url": WEBAPP_URL})]
    ]
    await update.message.reply_text(
        "🎰 Добро пожаловать в CRASH",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("👑 Админ-панель активна")

# ================== REGISTER ==================
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("admin", admin))

# ================== WEBHOOK ==================
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

# ================== STARTUP ==================
@app.on_event("startup")
async def on_startup():
    await tg_app.initialize()
    await tg_app.bot.set_webhook(WEBHOOK_URL)
    logging.info("🤖 Webhook установлен")

@app.on_event("shutdown")
async def on_shutdown():
    await tg_app.bot.delete_webhook()
    await tg_app.shutdown()

@app.get("/")
async def root():
    return {"status": "ok"}
