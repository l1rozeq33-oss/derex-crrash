import os, asyncio, random, requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

SUPABASE_URL = "https://gppcrpilqoskvczzqxog.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdwcGNycGlscW9za3ZjenpxeG9nIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1MzkzMTgsImV4cCI6MjA4MzExNTMxOH0.vGlpLwQXC9Cmj-mMyXAKXszYkQlILjipcDzM-IlpXNI"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

app = FastAPI()

# ================== SUPABASE BALANCE ==================
def get_balance(uid: int) -> float:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/users?id=eq.{uid}&select=balance",
        headers=HEADERS
    ).json()

    if not r:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/users",
            headers=HEADERS,
            json={"id": uid, "balance": 0}
        )
        return 0.0

    return float(r[0]["balance"])


def set_balance(uid: int, value: float):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/users?id=eq.{uid}",
        headers=HEADERS,
        json={"balance": round(value, 2)}
    )

# ================== BOT ==================
bot = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🚀 Играть в Crash", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        "🎰 DEREX CASINO\nДобро пожаловать!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def give(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(ctx.args[0])
    amt = float(ctx.args[1])
    set_balance(uid, get_balance(uid) + amt)
    await update.message.reply_text("✅ Баланс выдан")

bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("give", give))

# ================== GAME ==================
GAME = {
    "state": "waiting",
    "x": 1.0,
    "crash": 0,
    "bets": {},
    "online": random.randint(15, 35),
    "history": [],
    "timer": 5
}

async def game_loop():
    while True:
        GAME["state"] = "waiting"
        GAME["bets"] = {}
        GAME["x"] = 1.0

        for i in range(5, 0, -1):
            GAME["timer"] = i
            await asyncio.sleep(1)

        GAME["state"] = "flying"
        GAME["timer"] = 0
        GAME["crash"] = round(random.uniform(1.3, 7), 2)

        while GAME["x"] < GAME["crash"]:
            GAME["x"] = round(GAME["x"] + 0.02, 2)
            await asyncio.sleep(0.12)

        GAME["state"] = "crashed"
        GAME["history"].insert(0, GAME["crash"])
        GAME["history"] = GAME["history"][:10]

        await asyncio.sleep(0.5)

# ================== FASTAPI ==================
@app.on_event("startup")
async def startup():
    await bot.initialize()
    await bot.bot.set_webhook(f"{WEBAPP_URL}/webhook")
    asyncio.create_task(game_loop())

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    await bot.process_update(Update.de_json(data, bot.bot))
    return {"ok": True}

@app.get("/state")
def state():
    return GAME

@app.post("/bet")
async def bet(d: dict):
    uid, amt = int(d["uid"]), float(d["amount"])
    if GAME["state"] != "waiting": return {"error": 1}
    if uid in GAME["bets"]: return {"error": 3}
    if get_balance(uid) < amt: return {"error": 2}
    set_balance(uid, get_balance(uid) - amt)
    GAME["bets"][uid] = amt
    return {"ok": True}

@app.post("/cashout")
async def cashout(d: dict):
    uid = int(d["uid"])
    if GAME["state"] != "flying" or uid not in GAME["bets"]:
        return {"error": 1}
    win = GAME["bets"].pop(uid) * GAME["x"]
    set_balance(uid, get_balance(uid) + win)
    return {"win": round(win, 2)}

@app.get("/balance/{uid}")
def bal(uid: int):
    return {"balance": get_balance(uid)}

# ================== MINI APP ==================
@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
</head>
<body style="background:#0b0e14;color:#fff;font-family:Arial;text-align:center">
<h2>🚀 DEREX CRASH</h2>
<p>Мини-апп работает. Баланс сохраняется навсегда.</p>
</body>
</html>"""
