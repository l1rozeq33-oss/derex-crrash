import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ================== НАСТРОЙКИ ИЗ ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")          # токен бота
OWNER_ID = int(os.getenv("OWNER_ID", "0"))  # твой Telegram ID
DOMAIN = os.getenv("DOMAIN")                # https://xxxx.onrender.com

if not BOT_TOKEN or not DOMAIN:
    raise RuntimeError("❌ BOT_TOKEN или DOMAIN не заданы в Environment Variables")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{DOMAIN}{WEBHOOK_PATH}"

# ================== FASTAPI ==================
app = FastAPI()

# ================== TELEGRAM APP ==================
telegram_app = Application.builder().token(BOT_TOKEN).build()

# ================== КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 Играть в Crash",
                web_app=WebAppInfo(url=DOMAIN),
            )
        ]
    ]
    await update.message.reply_text(
        "Добро пожаловать в Crash Casino 🎰\n\nНажми кнопку ниже 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

telegram_app.add_handler(CommandHandler("start", start))

# ================== WEBHOOK ==================
@app.on_event("startup")
async def on_startup():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(WEBHOOK_URL)
    print("🤖 Webhook установлен:", WEBHOOK_URL)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

# ================== MINI APP (CRASH UI) ==================
@app.get("/", response_class=HTMLResponse)
async def mini_app():
    return """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Crash</title>
<style>
body {
    margin: 0;
    background: #0e0e0e;
    color: white;
    font-family: Arial, sans-serif;
    text-align: center;
}
#multiplier {
    font-size: 48px;
    margin-top: 40px;
}
button {
    padding: 15px 30px;
    font-size: 18px;
    border: none;
    border-radius: 8px;
    background: #ff2e63;
    color: white;
    cursor: pointer;
}
</style>
</head>
<body>
<h2>Crash</h2>
<div id="multiplier">1.00x</div>
<br>
<button onclick="startGame()">СТАВКА</button>

<script>
let running = false;
let value = 1.0;
let timer;

function startGame() {
    if (running) return;
    running = true;
    value = 1.0;
    document.getElementById("multiplier").innerText = value.toFixed(2) + "x";

    timer = setInterval(() => {
        value += 0.05;
        document.getElementById("multiplier").innerText = value.toFixed(2) + "x";

        if (Math.random() < 0.02) {
            clearInterval(timer);
            running = false;
            alert("💥 КРАШ НА " + value.toFixed(2) + "x");
        }
    }, 100);
}
</script>
</body>
</html>
"""
