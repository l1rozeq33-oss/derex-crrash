import os, json, random, asyncio, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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
    "history": []
}
bets = {}
online = random.randint(10, 40)

# ===== BOT =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in users:
        users[uid] = {"balance": 0}
        save()

    kb = [[InlineKeyboardButton("🚀 Играть в Crash", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        f"💰 Баланс: {users[uid]['balance']}$",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid, amount = context.args
    if uid not in users:
        users[uid] = {"balance": 0}
    users[uid]["balance"] += float(amount)
    save()
    await update.message.reply_text(f"✅ Выдано {amount}$ пользователю {uid}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = context.args[0]
    bal = users.get(uid, {"balance": 0})["balance"]
    await update.message.reply_text(f"💰 Баланс {uid}: {bal}$")

tg.add_handler(CommandHandler("start", start))
tg.add_handler(CommandHandler("give", give))
tg.add_handler(CommandHandler("balance", balance))

@app.post("/webhook")
async def webhook(req: Request):
    update = Update.de_json(await req.json(), tg.bot)
    await tg.process_update(update)
    return {"ok": True}

# ===== MINI APP =====
@app.get("/", response_class=HTMLResponse)
async def miniapp():
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body {{
margin:0;
background:radial-gradient(circle at top,#1b1f33,#090c16);
color:white;
font-family:Arial;
display:flex;
justify-content:center;
align-items:center;
height:100vh;
}}
#box {{
width:360px;
text-align:center;
}}
#top {{
display:flex;
justify-content:space-between;
margin-bottom:10px;
}}
#game {{
height:220px;
position:relative;
}}
#rocket {{
position:absolute;
left:50%;
bottom:20px;
transform:translateX(-50%);
font-size:48px;
transition:transform .12s linear;
}}
#x {{
position:absolute;
left:50%;
bottom:90px;
transform:translateX(-50%);
font-size:36px;
font-weight:bold;
}}
#crash {{
display:none;
color:#ff4d4d;
font-size:32px;
font-weight:bold;
}}
button,input {{
width:100%;
padding:14px;
border:none;
border-radius:12px;
font-size:16px;
margin-top:8px;
}}
#bet {{
background:#2b2f45;
color:white;
}}
#cash {{
background:#f39c12;
color:black;
display:none;
}}
</style>
</head>
<body>

<div id="box">
<div id="top">
<div>💰 <span id="bal">0$</span></div>
<div>👥 {online}</div>
</div>

<div id="game">
<div id="x">x1.00</div>
<div id="crash">CRASH</div>
<div id="rocket">🚀</div>
</div>

<input id="amount" type="number" value="10" min="1">
<button id="bet" onclick="bet()">СДЕЛАТЬ СТАВКУ</button>
<button id="cash" onclick="cash()">CASHOUT</button>

<div style="margin-top:10px">📊 <span id="hist"></span></div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
let staked=false;

function update(){{
fetch("/api/state?u="+tg.initDataUnsafe.user.id)
.then(r=>r.json())
.then(d=>{{
bal.innerText=d.b+"$";
x.innerText="x"+d.x.toFixed(2);
hist.innerText=d.h.join(" ");
if(d.running){{
crash.style.display="none";
rocket.style.transform="translateX(-50%) translateY("+(-d.x*22)+"px)";
if(staked) cash.style.display="block";
}} else {{
cash.style.display="none";
rocket.style.transform="translateX(-50%) translateY(-260px)";
crash.style.display="block";
staked=false;
}}
}});
}}
setInterval(update,120);

function bet(){{
fetch("/api/bet",{{method:"POST",headers:{{"Content-Type":"application/json"}},
body:JSON.stringify({{u:tg.initDataUnsafe.user.id,a:amount.value}})}});
staked=true;
}}

function cash(){{
fetch("/api/cash",{{method:"POST",headers:{{"Content-Type":"application/json"}},
body:JSON.stringify({{u:tg.initDataUnsafe.user.id}})}});
staked=false;
}}
</script>
</body>
</html>
"""

# ===== API =====
@app.get("/api/state")
async def api_state(u: str):
    if u not in users:
        users[u] = {"balance": 0}
        save()
    return {
        "x": state["x"],
        "running": state["running"],
        "b": users[u]["balance"],
        "h": state["history"][-8:]
    }

@app.post("/api/bet")
async def api_bet(d: dict):
    u = str(d["u"])
    a = float(d["a"])
    if users[u]["balance"] < a:
        return {}
    bets[u] = a
    users[u]["balance"] -= a
    save()
    return {}

@app.post("/api/cash")
async def api_cash(d: dict):
    u = str(d["u"])
    if u not in bets or not state["running"]:
        return {}
    win = round(bets.pop(u) * state["x"], 2)
    users[u]["balance"] += win
    save()
    return {}

# ===== GAME LOOP =====
async def game_loop():
    while True:
        state["x"] = 1.0
        state["crash"] = round(random.uniform(1.4, 6), 2)
        state["running"] = True
        while state["x"] < state["crash"]:
            await asyncio.sleep(0.12)
            state["x"] += 0.02
        state["running"] = False
        state["history"].append(state["crash"])
        bets.clear()
        await asyncio.sleep(3)

@app.on_event("startup")
async def start_all():
    await tg.initialize()
    await tg.bot.set_webhook(WEBAPP_URL + "/webhook")
    asyncio.create_task(game_loop())
