import os
import json
import random
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from supabase import create_client

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ================= FASTAPI =================
app = FastAPI()

# ================= STATE =================
state = {
    "state": "waiting",
    "timer": 5,
    "x": 1.00,
    "bets": {},
    "online": random.randint(10, 40)
}

# ================= SUPABASE HELPERS =================
def get_balance(uid: str):
    res = supabase.table("balances").select("balance").eq("id", uid).execute()
    if res.data:
        return float(res.data[0]["balance"])
    supabase.table("balances").insert({"id": uid, "balance": 100}).execute()
    return 100.0

def set_balance(uid: str, amount: float):
    supabase.table("balances").upsert({"id": uid, "balance": amount}).execute()

# ================= GAME LOOP =================
async def game_loop():
    while True:
        state["state"] = "waiting"
        state["timer"] = 5
        state["bets"] = {}
        state["x"] = 1.00
        state["online"] = random.randint(10, 40)

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
        await asyncio.sleep(1)

# ================= TELEGRAM BOT =================
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Derex Crash",
        reply_markup={
            "inline_keyboard": [[
                {"text": "🎮 Играть", "web_app": {"url": WEBAPP_URL}}
            ]]
        }
    )

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = context.args[0]
        amt = float(context.args[1])
        bal = get_balance(uid)
        set_balance(uid, bal + amt)
        await update.message.reply_text(f"✅ Выдано {amt}$ пользователю {uid}")
    except:
        await update.message.reply_text("❌ /give <tg_id> <amount>")

tg_app.add_handler(CommandHandler("start", start_cmd))
tg_app.add_handler(CommandHandler("give", give_cmd))

# ================= WEBHOOK =================
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def startup():
    asyncio.create_task(game_loop())
    await tg_app.initialize()
    await tg_app.bot.set_webhook(f"{WEBAPP_URL}/webhook")

# ================= API =================
@app.get("/state")
def api_state():
    return state

@app.get("/balance/{uid}")
def api_balance(uid: str):
    return {"balance": get_balance(uid)}

@app.post("/bet")
async def bet(data: dict):
    uid = str(data["uid"])
    amt = float(data["amount"])
    if state["state"] != "waiting":
        return {"error": "started"}
    bal = get_balance(uid)
    if bal < amt:
        return {"error": "no money"}
    set_balance(uid, bal - amt)
    state["bets"][uid] = amt
    return {"ok": True}

@app.post("/cashout")
async def cashout(data: dict):
    uid = str(data["uid"])
    if uid not in state["bets"]:
        return {"error": "no bet"}
    win = round(state["bets"][uid] * state["x"], 2)
    bal = get_balance(uid)
    set_balance(uid, bal + win)
    del state["bets"][uid]
    return {"win": win, "x": state["x"]}

# ================= UI =================
@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{
 margin:0;
 background:linear-gradient(120deg,#020617,#0f172a,#020617);
 background-size:400% 400%;
 animation:bg 10s infinite;
 color:white;
 font-family:Arial;
}
@keyframes bg{
 0%{background-position:0% 50%}
 50%{background-position:100% 50%}
 100%{background-position:0% 50%}
}
#app{padding:16px;height:100vh;display:flex;flex-direction:column;justify-content:space-between}
.badge{background:#020617aa;padding:8px 16px;border-radius:20px}
.center{text-align:center}
.rocket{font-size:100px;transition:.12s}
button,input{width:100%;padding:18px;border-radius:16px;border:none;font-size:18px;margin-top:8px}
button{background:#2563eb;color:white}
#cash{background:orange;color:black;display:none}
.menu{display:flex;justify-content:space-around;padding:12px}
.toast{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#22c55e;color:black;padding:10px 20px;border-radius:20px;display:none}
</style>
</head>
<body>
<div class="toast" id="toast"></div>
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
  <div onclick="alert('Автоматическое зачисление средств временно недоступно.\\nПишите @DerexSupport')">➕ Пополнить</div>
  <div onclick="alert('Автоматический вывод временно недоступен.\\nПишите @DerexSupport')">💸 Вывести</div>
 </div>
</div>

<script>
const tg=Telegram.WebApp;tg.expand();
const uid=tg.initDataUnsafe.user.id;
let cashed=false;

function toast(t){let x=document.getElementById('toast');x.innerText=t;x.style.display='block';setTimeout(()=>x.style.display='none',2500)}

async function tick(){
 let s=await fetch('/state').then(r=>r.json());
 let b=await fetch('/balance/'+uid).then(r=>r.json());
 on.innerText=s.online;
 bal.innerText=b.balance.toFixed(2);
 x.innerText=s.x.toFixed(2)+'x';
 timer.innerText=s.state=='waiting'?'Старт через '+s.timer:'';

 if(s.state=='flying'){
  rocket.style.transform='translateY(-'+(s.x*6)+'px)';
  bet.style.display='none';
  if(s.bets && s.bets[uid] && !cashed){
   cash.style.display='block';
   cash.innerText='Вывести '+(s.bets[uid]*s.x).toFixed(2)+'$';
  }
 }

 if(s.state=='waiting'){
  rocket.style.transform='translateY(0)';
  bet.style.display='block';
  cash.style.display='none';
  cashed=false;
 }

 if(s.state=='crashed'){
  rocket.innerText='💥';
  cash.style.display='none';
  cashed=true;
 }
}

setInterval(tick,120);

bet.onclick=()=>fetch('/bet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid,amount:+amt.value})});
cash.onclick=async()=>{
 cashed=true;cash.style.display='none';
 let r=await fetch('/cashout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid})}).then(r=>r.json());
 toast('+'+r.win+'$ @ '+r.x+'x');
}
</script>
</body>
</html>
"""
