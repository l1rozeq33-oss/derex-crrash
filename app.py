import os, json, random, asyncio
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

# ==== GAME STATE ====
current_x = 1.0
crash_x = 2.0
round_active = False
bets = {}
history = []

# ==== BOT ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid not in users:
        users[uid] = {"balance": 1000}
        save()

    kb = [[InlineKeyboardButton("🚀 Играть", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        f"💰 Баланс: {users[uid]['balance']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

tg.add_handler(CommandHandler("start", start))

# ==== WEBHOOK ====
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg.bot)
    await tg.process_update(update)
    return {"ok": True}

# ==== MINI APP ====
@app.get("/", response_class=HTMLResponse)
async def miniapp():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{background:#0b0f1a;color:white;font-family:Arial;text-align:center}
#top{display:flex;justify-content:space-around;margin:10px}
canvas{background:#111;border-radius:10px}
button,input{padding:10px;margin:5px;font-size:16px}
</style>
</head>
<body>

<div id="top">
<div>👥 Онлайн: <span id="online">---</span></div>
<div>📊 История: <span id="hist">---</span></div>
</div>

<h1 id="x">x1.00</h1>
<canvas id="c" width="300" height="150"></canvas><br>

<input id="bet" type="number" value="10" min="1"><br>
<button onclick="bet()">СТАВКА</button>
<button onclick="cash()">CASHOUT</button>

<script>
const tg = Telegram.WebApp; tg.expand();
let ctx = c.getContext("2d");
let x = 1.0, run=false;

function draw(){
 ctx.clearRect(0,0,300,150);
 ctx.beginPath();
 ctx.moveTo(0,150);
 ctx.lineTo(x*40,150-x*20);
 ctx.strokeStyle="lime";
 ctx.stroke();
}

function loop(){
 if(!run) return;
 x+=0.01;
 document.getElementById("x").innerText="x"+x.toFixed(2);
 draw();
 setTimeout(loop,100);
}

function bet(){
 fetch("/api/bet",{method:"POST",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({u:tg.initDataUnsafe.user.id,a:bet.value})});
 x=1;run=true;loop();
}

function cash(){
 run=false;
 fetch("/api/cash",{method:"POST",headers:{"Content-Type":"application/json"},
 body:JSON.stringify({u:tg.initDataUnsafe.user.id,x:x})});
}

setInterval(()=>{
 document.getElementById("online").innerText =
 Math.floor(120+Math.random()*300);
 fetch("/api/state").then(r=>r.json()).then(d=>{
 document.getElementById("hist").innerText=d.h.join(" ");
 });
},2000);
</script>
</body>
</html>
"""

# ==== API ====
@app.post("/api/bet")
async def bet(d:dict):
    u=str(d["u"]); a=float(d["a"])
    if users[u]["balance"]<a: return {"err":1}
    users[u]["balance"]-=a
    bets[u]=a
    save()
    return {"ok":1}

@app.post("/api/cash")
async def cash(d:dict):
    u=str(d["u"]); x=float(d["x"])
    if u not in bets: return {}
    if x>=crash_x:
        bets.pop(u)
        return {"crash":1}
    win=round(bets.pop(u)*x,2)
    users[u]["balance"]+=win
    save()
    return {"win":win}

@app.get("/api/state")
async def state():
    return {"h":history[-10:]}

# ==== GAME LOOP ====
async def game():
    global current_x, crash_x
    while True:
        current_x=1
        crash_x=round(random.uniform(1.3,5),2)
        while current_x<crash_x:
            await asyncio.sleep(0.1)
            current_x+=0.01
        history.append(crash_x)
        bets.clear()
        await asyncio.sleep(3)

@app.on_event("startup")
async def start_all():
    await tg.initialize()
    await tg.bot.set_webhook(WEBAPP_URL+"/webhook")
    asyncio.create_task(game())
