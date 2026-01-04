import asyncio
import random
import threading

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "ВСТАВЬ_ТОКЕН_БОТА"
ADMIN_ID = 7963516753

MIN_BET = 0.5
MAX_BET = 20000

# ================== FASTAPI ==================
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

clients = []
balances = {}
bets = {}

multiplier = 1.0
crash_at = 0
round_active = False


# ================== GAME LOOP ==================
async def game_loop():
    global multiplier, crash_at, round_active, bets

    while True:
        await asyncio.sleep(6)

        multiplier = 1.0
        crash_at = round(random.uniform(1.5, 8.0), 2)
        round_active = True
        bets = {}

        while multiplier < crash_at:
            multiplier = round(multiplier + 0.02, 2)
            for ws in clients:
                await ws.send_json({
                    "type": "update",
                    "multiplier": multiplier
                })
            await asyncio.sleep(0.08)

        round_active = False
        for ws in clients:
            await ws.send_json({
                "type": "crash",
                "multiplier": crash_at
            })


@app.on_event("startup")
async def startup():
    asyncio.create_task(game_loop())


# ================== WEBSOCKET ==================
@app.websocket("/ws")
async def websocket(ws: WebSocket):
    await ws.accept()
    clients.append(ws)

    try:
        while True:
            data = await ws.receive_json()
            uid = str(data["user_id"])

            balances.setdefault(uid, 100.0)

            if data["action"] == "bet":
                amount = float(data["amount"])
                if not round_active:
                    continue
                if amount < MIN_BET or amount > MAX_BET:
                    continue
                if balances[uid] < amount:
                    continue

                balances[uid] -= amount
                bets[uid] = {"amount": amount, "cashed": False}

            if data["action"] == "cashout":
                if uid in bets and not bets[uid]["cashed"] and round_active:
                    win = round(bets[uid]["amount"] * multiplier, 2)
                    balances[uid] += win
                    bets[uid]["cashed"] = True
    except:
        clients.remove(ws)


# ================== MINI APP (UI как 1win) ==================
@app.get("/")
async def index():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Derex Crash</title>
<style>
body {
  margin:0;
  background:#0b0f1a;
  color:#fff;
  font-family:Arial;
  text-align:center;
}
.header {
  padding:15px;
  font-size:22px;
  font-weight:bold;
  background:#0f1526;
}
.mult {
  font-size:48px;
  margin:20px 0;
  color:#00ffcc;
}
.rocket {
  font-size:90px;
  transition: transform 0.1s linear;
}
.panel {
  background:#11182d;
  padding:15px;
  position:fixed;
  bottom:0;
  width:100%;
}
input {
  padding:10px;
  font-size:18px;
  width:120px;
  border-radius:6px;
  border:none;
}
button {
  padding:12px 20px;
  font-size:18px;
  border:none;
  border-radius:6px;
  margin:5px;
  cursor:pointer;
}
.bet { background:#1f9cff; color:white; }
.cash { background:#00c853; color:white; }
</style>
</head>
<body>

<div class="header">🚀 DerexCrash</div>

<div class="mult" id="x">x1.00</div>
<div class="rocket" id="rocket">🚀</div>

<div class="panel">
  <input id="bet" type="number" value="10" min="0.5">
  <button class="bet" onclick="bet()">Ставка</button>
  <button class="cash" onclick="cashout()">Забрать</button>
</div>

<script>
const tg = window.Telegram.WebApp;
const user = tg.initDataUnsafe.user;
const ws = new WebSocket("wss://" + location.host + "/ws");

ws.onmessage = (e) => {
  const d = JSON.parse(e.data);
  if (d.type === "update") {
    document.getElementById("x").innerText = "x" + d.multiplier.toFixed(2);
    document.getElementById("rocket").style.transform =
      "translateY(" + (-d.multiplier * 18) + "px)";
  }
  if (d.type === "crash") {
    alert("💥 CRASH x" + d.multiplier);
  }
};

function bet() {
  ws.send(JSON.stringify({
    action:"bet",
    user_id:user.id,
    amount:document.getElementById("bet").value
  }));
}

function cashout() {
  ws.send(JSON.stringify({
    action:"cashout",
    user_id:user.id
  }));
}
</script>

</body>
</html>
""")


# ================== TELEGRAM BOT ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🚀 Играть в Crash",
            web_app=WebAppInfo(url="https://ТВОЙ_ДОМЕН")
        )]
    ])

    await update.message.reply_text(
        "🎰 *DerexCasino*\n\n"
        "🚀 Добро пожаловать в Crash!\n"
        "Сделай ставку и забери выигрыш вовремя 💸",
        parse_mode="Markdown",
        reply_markup=kb
    )


def run_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.run_polling()


threading.Thread(target=run_bot, daemon=True).start()

# ================== ЗАПУСК ==================
# uvicorn app:app --host 0.0.0.0 --port 10000
