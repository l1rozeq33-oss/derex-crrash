import os
import asyncio
import random
import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")


# ---------- FASTAPI ----------
app = FastAPI()


# ---------- DATABASE ----------
db = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = db.cursor()
cur.execute(
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL)"
)
db.commit()


def balance(uid: int) -> float:
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users VALUES (?, ?)", (uid, 0))
        db.commit()
        return 0.0
    return float(row[0])


def set_balance(uid: int, value: float):
    cur.execute("UPDATE users SET balance=? WHERE id=?", (value, uid))
    db.commit()


# ---------- BOT ----------
bot = ApplicationBuilder().token(BOT_TOKEN).build()


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton(
            "🚀 Играть в Crash",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]]
    await update.message.reply_text(
        "🎰 DEREX CASINO\n\nДобро пожаловать!",
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def give(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    uid = int(ctx.args[0])
    amt = float(ctx.args[1])

    set_balance(uid, balance(uid) + amt)
    await update.message.reply_text("✅ Баланс начислен")


bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("give", give))


# ---------- GAME ----------
GAME = {
    "state": "waiting",
    "x": 1.0,
    "crash": 0.0,
    "bets": {},
    "online": random.randint(10, 40),
    "history": [],
    "timer": 5
}


async def game_loop():
    while True:
        # WAITING
        GAME["state"] = "waiting"
        GAME["bets"] = {}
        GAME["x"] = 1.0

        for i in range(5, 0, -1):
            GAME["timer"] = i
            await asyncio.sleep(1)

        # FLYING
        GAME["state"] = "flying"
        GAME["timer"] = 0
        GAME["crash"] = round(random.uniform(1.3, 7.0), 2)

        while GAME["x"] < GAME["crash"]:
            GAME["x"] = round(GAME["x"] + 0.02, 2)
            await asyncio.sleep(0.12)

        # CRASH
        GAME["state"] = "crashed"
        GAME["history"].insert(0, GAME["crash"])
        GAME["history"] = GAME["history"][:10]

        await asyncio.sleep(0.6)


# ---------- FASTAPI LIFECYCLE ----------
@app.on_event("startup")
async def startup():
    await bot.initialize()
    await bot.bot.set_webhook(f"{WEBAPP_URL}/webhook")
    asyncio.create_task(game_loop())


# ---------- WEBHOOK (ЭТО БЫЛО ГЛАВНОЕ, ЧЕГО НЕ ХВАТАЛО) ----------
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    await bot.process_update(Update.de_json(data, bot.bot))
    return {"ok": True}


# ---------- API ----------
@app.get("/state")
def state():
    return GAME


@app.post("/bet")
async def bet(d: dict):
    uid = int(d["uid"])
    amt = float(d["amount"])

    if GAME["state"] != "waiting":
        return {"error": 1}
    if uid in GAME["bets"]:
        return {"error": 3}
    if balance(uid) < amt:
        return {"error": 2}

    set_balance(uid, balance(uid) - amt)
    GAME["bets"][uid] = amt
    return {"ok": True}


@app.post("/cashout")
async def cashout(d: dict):
    uid = int(d["uid"])

    if GAME["state"] != "flying" or uid not in GAME["bets"]:
        return {"error": 1}

    win = GAME["bets"].pop(uid) * GAME["x"]
    set_balance(uid, balance(uid) + win)
    return {"win": round(win, 2)}


@app.get("/balance/{uid}")
def bal(uid: int):
    return {"balance": balance(uid)}


# ---------- MINI APP ----------
@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>

<!-- ТВОЙ HTML И CSS БЕЗ ИЗМЕНЕНИЙ -->
<!-- Я ЕГО НЕ ТРОГАЮ -->

</head>
<body>
ТУТ ТВОЙ ТЕКУЩИЙ HTML (ОН УЖЕ РАБОЧИЙ)
</body>
</html>
"""
