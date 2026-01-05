import json
import random
import asyncio
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = FastAPI()

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

# ================== FILES ==================
BAL_FILE = "balances.json"
HIST_FILE = "history.json"

def load(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

balances = load(BAL_FILE, {})
history = load(HIST_FILE, {})

# ================== GAME STATE ==================
state = {
    "state": "waiting",
    "timer": 5,
    "x": 1.00,
    "bets": {},
    "online": random.randint(80, 160)
}

# ================== GAME LOOP ==================
async def game_loop():
    while True:
        state["state"] = "waiting"
        state["timer"] = 5
        state["bets"] = {}
        state["x"] = 1.00

        for i in range(5, 0, -1):
            state["timer"] = i
            await asyncio.sleep(1)

        state["state"] = "flying"

        crash_at = random.choice(
            [round(random.uniform(1.0, 1.3), 2)] * 4 +
            [round(random.uniform(1.5, 4.5), 2)]
        )

        while state["x"] < crash_at:
            state["x"] = round(state["x"] + 0.01, 2)
            await asyncio.sleep(0.12)

        state["state"] = "crashed"

        for uid, bet in state["bets"].items():
            history.setdefault(uid, []).append({
                "bet": bet,
                "result": "crash",
                "x": state["x"]
            })

        save(HIST_FILE, history)
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup():
    asyncio.create_task(game_loop())

# ================== API ==================
@app.get("/state")
def get_state():
    return state

@app.get("/balance/{uid}")
def get_balance(uid: str):
    if uid not in balances:
        balances[uid] = 100.0
        save(BAL_FILE, balances)
    return {"balance": balances[uid]}

@app.post("/bet")
async def bet(data: dict):
    uid = str(data["uid"])
    amt = float(data["amount"])

    if state["state"] != "waiting":
        return {"error": "round started"}

    if balances.get(uid, 0) < amt:
        return {"error": "no money"}

    balances[uid] -= amt
    state["bets"][uid] = amt
    save(BAL_FILE, balances)
    return {"ok": True}

@app.post("/cashout")
async def cashout(data: dict):
    uid = str(data["uid"])

    if uid not in state["bets"]:
        return {"error": "no bet"}

    win = round(state["bets"][uid] * state["x"], 2)
    balances[uid] = balances.get(uid, 0) + win

    history.setdefault(uid, []).append({
        "bet": state["bets"][uid],
        "result": "win",
        "x": state["x"]
    })

    del state["bets"][uid]
    save(BAL_FILE, balances)
    save(HIST_FILE, history)

    return {"win": win}

@app.get("/history/{uid}")
def get_history(uid: str):
    return history.get(uid, [])

# ================== TELEGRAM BOT ==================
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎰 DerexCasino\n\nНажми кнопку ниже 👇",
        reply_markup={
            "inline_keyboard": [[
                {
                    "text": "🚀 Открыть Crash",
                    "web_app": {"url": WEBAPP_URL}
                }
            ]]
        }
    )

tg_app.add_handler(CommandHandler("start", start_cmd))

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

# ================== MINI APP ==================
@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<title>DerexCasino</title>

<style>
body{
 margin:0;
 background:radial-gradient(circle at top,#111827,#020617);
 color:#fff;
 font-family:Arial;
 overflow:hidden;
}
h1{opacity:.15;position:fixed;top:40%;left:50%;transform:translate(-50%,-50%);font-size:64px}
#app{padding:16px;height:100vh;display:flex;flex-direction:column;justify-content:space-between}
.badge{background:#111827;padding:8px 16px;border-radius:20px}
.center{text-align:center}
.rocket{font-size:110px;transition:.12s}
input,button{width:100%;padding:18px;border-radius:16px;border:none;font-size:20px;margin-top:10px}
input{background:#0f172a;color:#38bdf8}
button{background:#2563eb;color:white}
#cash{background:#22c55e;color:black;display:none}
.menu{display:flex;justify-content:space-around;background:#020617;padding:14px}
.menu div{opacity:.8}
</style>
</head>

<body>
<h1>DerexCasino</h1>
<div id="app">
 <div style="display:flex;justify-content:space-between">
  <div class="badge">👥 <span id="on"></span></div>
  <div class="badge">💰 <span id="bal"></span>$</div>
 </div>

 <div class="center">
  <div id="timer"></div>
  <div class="rocket" id="rocket">🚀</div>
  <div id="x">1.00x</div>
 </div>

 <div>
  <input id="amt" type="number" value="10">
  <button id="bet">Сделать ставку</button>
  <button id="cash"></button>
 </div>

 <div class="menu">
  <div onclick="alert('История скоро')">🏆 Топ</div>
  <div>🚀 Краш</div>
  <div onclick="alert('ID: '+uid)">👤 Профиль</div>
 </div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;
let cashed=false;

async function tick(){
 let s=await fetch("/state").then(r=>r.json());
 let b=await fetch("/balance/"+uid).then(r=>r.json());

 on.innerText=s.online;
 bal.innerText=b.balance.toFixed(2);
 x.innerText=s.x.toFixed(2)+"x";
 timer.innerText=s.state=="waiting"?"Старт через "+s.timer:"";

 if(s.state=="flying"){
  rocket.style.transform="translateY(-"+(s.x*5)+"px)";
  bet.style.display="none";
  if(s.bets && s.bets[uid] && !cashed){
   cash.style.display="block";
   cash.innerText="Вывести "+(s.bets[uid]*s.x).toFixed(2)+"$";
  }
 }

 if(s.state=="waiting"){
  rocket.style.transform="translateY(0)";
  bet.style.display="block";
  cash.style.display="none";
  cashed=false;
 }

 if(s.state=="crashed"){
  rocket.innerText="💥";
  cash.style.display="none";
  cashed=true;
 }
}

setInterval(tick,120);

bet.onclick=()=>fetch("/bet",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify({uid,amount:+amt.value})});
cash.onclick=()=>{cashed=true;cash.style.display="none";fetch("/cashout",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify({uid})})};
</script>
</body>
</html>"""
