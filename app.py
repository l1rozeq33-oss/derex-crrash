import os, json, random, asyncio, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

DATA_FILE = "data.json"

def load():
    if not os.path.exists(DATA_FILE):
        return {}
    return json.load(open(DATA_FILE))

def save():
    json.dump(users, open(DATA_FILE, "w"))

users = load()

app = FastAPI()
tg = Application.builder().token(BOT_TOKEN).build()

# ===== GAME STATE =====
state = {
    "x": 1.0,
    "crash": 2.0,
    "running": False,
    "history": [],
    "start": time.time()
}
bets = {}

# ===== BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in users:
        users[uid] = {"balance": 0}
        save()

    kb = [[InlineKeyboardButton("🚀 Открыть Crash", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        f"💰 Баланс: {users[uid]['balance']}$",
        reply_markup=InlineKeyboardMarkup(kb)
    )

tg.add_handler(CommandHandler("start", start))

@app.post("/webhook")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.process_update(update)
    return {"ok": True}

# ===== MINI APP =====
@app.get("/", response_class=HTMLResponse)
async def miniapp():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{
margin:0;
background:radial-gradient(circle at top,#1a1f3c,#070b16);
color:white;
font-family:Arial;
text-align:center
}
#top{display:flex;justify-content:space-around;padding:10px}
#game{position:relative;height:200px}
#rocket{
position:absolute;
left:50%;
bottom:20px;
transform:translateX(-50%);
font-size:40px;
transition:transform .1s linear
}
#x{
position:absolute;
left:50%;
bottom:80px;
transform:translateX(-50%);
font-size:32px;
font-weight:bold
}
button,input{
padding:12px;
border:none;
border-radius:10px;
margin:5px;
font-size:16px
}
#cash{display:none;background:#2ecc71}
#bet{background:#3498db}
</style>
</head>
<body>

<div id="top">
<div>💰 <span id="bal">0$</span></div>
<div>👥 <span id="on">---</span></div>
</div>

<div id="game">
<div id="x">x1.00</div>
<div id="rocket">🚀</div>
</div>

<input id="amount" type="number" min="1" value="10"><br>
<button id="bet" onclick="bet()">СТАВКА</button>
<button id="cash" onclick="cash()">CASHOUT</button>

<div>📊 История: <span id="hist"></span></div>

<script>
const tg = Telegram.WebApp; tg.expand();
let staked=false;

function update(){
fetch("/api/state?u="+tg.initDataUnsafe.user.id)
.then(r=>r.json())
.then(d=>{
document.getElementById("x").innerText="x"+d.x.toFixed(2);
document.getElementById("rocket").style.transform=
"translateX(-50%) translateY("+(-d.x*20)+"px)";
document.getElementById("bal").innerText=d.b+"$";
document.getElementById("hist").innerText=d.h.join(" ");
document.getElementById("on").innerText=
Math.floor(150+Math.random()*300);
if(d.running && staked) cash.style.display="inline-block";
else cash.style.display="none";
});
}
setInterval(update,100);

function bet(){
fetch("/api/bet",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({
u:tg.initDataUnsafe.user.id,
a:amount.value
})});
staked=true;
}

function cash(){
fetch("/api/cash",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({u:tg.initDataUnsafe.user.id})});
staked=false;
}
</script>
</body>
</html>
"""

# ===== API =====
@app.get("/api/state")
async def api_state(u:str):
    if u not in users:
        users[u]={"balance":0}; save()
    return {
        "x": state["x"],
        "running": state["running"],
        "b": users[u]["balance"],
        "h": state["history"][-10:]
    }

@app.post("/api/bet")
async def api_bet(d:dict):
    u=str(d["u"]); a=float(d["a"])
    if users[u]["balance"]<a: return {}
    bets[u]=a
    users[u]["balance"]-=a
    save(); return {}

@app.post("/api/cash")
async def api_cash(d:dict):
    u=str(d["u"])
    if u not in bets or not state["running"]: return {}
    win=round(bets.pop(u)*state["x"],2)
    users[u]["balance"]+=win
    save(); return {}

# ===== GAME LOOP =====
async def game_loop():
    while True:
        state["x"]=1.0
        state["crash"]=round(random.uniform(1.3,6),2)
        state["running"]=True
        while state["x"]<state["crash"]:
            await asyncio.sleep(0.1)
            state["x"]+=0.02
        state["running"]=False
        state["history"].append(state["crash"])
        bets.clear()
        await asyncio.sleep(3)

@app.on_event("startup")
async def start_all():
    await tg.initialize()
    await tg.bot.set_webhook(WEBAPP_URL+"/webhook")
    asyncio.create_task(game_loop())
