import os
import random
import time
import threading
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

app = FastAPI()

# ================== GAME STORAGE ==================

balances = {}          # user_id -> balance
current_round = {
    "multiplier": 1.0,
    "crashed": False,
    "start_time": time.time(),
    "crash_point": random.uniform(1.5, 6.0)
}

bets = {}              # user_id -> bet_amount

# ================== GAME LOOP ==================

def game_loop():
    global current_round
    while True:
        current_round = {
            "multiplier": 1.0,
            "crashed": False,
            "start_time": time.time(),
            "crash_point": random.uniform(1.5, 6.0)
        }

        while current_round["multiplier"] < current_round["crash_point"]:
            time.sleep(0.1)
            current_round["multiplier"] += 0.02

        current_round["crashed"] = True
        bets.clear()
        time.sleep(3)

threading.Thread(target=game_loop, daemon=True).start()

# ================== API ==================

@app.get("/state")
def state():
    return current_round

@app.post("/bet")
async def bet(req: Request):
    data = await req.json()
    uid = int(data["user_id"])
    amount = int(data["amount"])

    balances.setdefault(uid, 1000)

    if balances[uid] < amount:
        return {"error": "NO_BALANCE"}

    balances[uid] -= amount
    bets[uid] = amount
    return {"ok": True}

@app.post("/cashout")
async def cashout(req: Request):
    data = await req.json()
    uid = int(data["user_id"])

    if uid not in bets or current_round["crashed"]:
        return {"error": "FAILED"}

    win = bets[uid] * current_round["multiplier"]
    balances[uid] += int(win)
    bets.pop(uid, None)

    return {"win": int(win), "balance": balances[uid]}

@app.get("/balance/{uid}")
def balance(uid: int):
    return {"balance": balances.get(uid, 1000)}

# ================== ADMIN ==================

@app.post("/admin/give")
async def admin_give(req: Request):
    data = await req.json()
    if int(data["admin_id"]) != ADMIN_ID:
        return {"error": "DENIED"}

    uid = int(data["user_id"])
    amount = int(data["amount"])
    balances[uid] = balances.get(uid, 1000) + amount
    return {"ok": True, "balance": balances[uid]}

# ================== MINI APP ==================

@app.get("/", response_class=HTMLResponse)
def miniapp():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Crash</title>
<style>
body { background:#0b0f1a;color:white;font-family:Arial;text-align:center }
#x { font-size:40px;margin:20px }
button { padding:10px 20px;border-radius:8px;border:none;background:#1f8cff;color:white;font-size:16px }
</style>
</head>
<body>

<h2>CRASH</h2>
<div id="x">1.00x</div>
<input id="bet" type="number" value="10"><br><br>
<button onclick="place()">СТАВКА</button>
<button onclick="cash()">CASHOUT</button>
<p id="bal"></p>

<script>
const tg = window.Telegram.WebApp;
tg.expand();
const uid = tg.initDataUnsafe.user.id;

function load() {
 fetch('/balance/'+uid).then(r=>r.json()).then(d=>{
  bal.innerText = "Баланс: "+d.balance
 })
}
load();

setInterval(()=>{
 fetch('/state').then(r=>r.json()).then(d=>{
  x.innerText = d.multiplier.toFixed(2)+"x"
 })
},100);

function place(){
 fetch('/bet',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({user_id:uid,amount:bet.value})}).then(load)
}

function cash(){
 fetch('/cashout',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({user_id:uid})}).then(r=>r.json()).then(d=>{
  if(d.win) alert("WIN "+d.win)
  load()
 })
}
</script>
</body>
</html>
"""

# ================== BOT ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🚀 Играть", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text("Crash", reply_markup=InlineKeyboardMarkup(kb))

def run_bot():
    appb = ApplicationBuilder().token(BOT_TOKEN).build()
    appb.add_handler(CommandHandler("start", start))
    appb.run_polling(close_loop=False)

threading.Thread(target=run_bot, daemon=True).start()
