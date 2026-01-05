import os, json, asyncio, random
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

app = FastAPI()

# ================== BALANCES (FOREVER) ==================
BAL_FILE = "balances.json"

def load_balances():
    if not os.path.exists(BAL_FILE):
        return {}
    with open(BAL_FILE, "r") as f:
        return json.load(f)

def save_balances(b):
    with open(BAL_FILE, "w") as f:
        json.dump(b, f)

balances = load_balances()

def balance(uid):
    return float(balances.get(str(uid), 0))

def add_balance(uid, amt):
    uid = str(uid)
    balances[uid] = balance(uid) + amt
    save_balances(balances)

def sub_balance(uid, amt):
    uid = str(uid)
    balances[uid] = balance(uid) - amt
    save_balances(balances)

# ================== BOT ==================
bot = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🚀 Играть в Crash", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        "🎰 **DEREX CASINO**\nCrash-игра",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def give(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = ctx.args[0]
        amt = float(ctx.args[1])
        add_balance(uid, amt)
        await update.message.reply_text(f"✅ Выдано {amt}$ пользователю {uid}")
    except:
        await update.message.reply_text("❌ /give <tg_id> <amount>")

bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("give", give))

# ================== GAME ==================
GAME = {
    "state": "waiting",
    "x": 1.0,
    "crash": 1.0,
    "bets": {},
    "history": [],
    "online": random.randint(25, 70),
    "timer": 5
}

def gen_crash():
    r = random.random()
    if r < 0.25: return 1.00
    if r < 0.40: return 1.30
    if r < 0.55: return 1.60
    return round(random.uniform(2, 6), 2)

async def game_loop():
    while True:
        GAME["state"] = "waiting"
        GAME["bets"] = {}
        GAME["x"] = 1.0

        for i in range(5, 0, -1):
            GAME["timer"] = i
            await asyncio.sleep(1)

        GAME["state"] = "flying"
        GAME["crash"] = gen_crash()

        while GAME["x"] < GAME["crash"]:
            GAME["x"] = round(GAME["x"] + 0.01, 2)
            await asyncio.sleep(0.12)

        GAME["state"] = "crashed"
        GAME["history"].insert(0, GAME["crash"])
        GAME["history"] = GAME["history"][:10]
        await asyncio.sleep(0.6)

# ================== FASTAPI ==================
@app.on_event("startup")
async def startup():
    await bot.initialize()
    await bot.bot.set_webhook(WEBAPP_URL + "/webhook")
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
    uid = str(d["uid"])
    amt = float(d["amount"])
    if GAME["state"] != "waiting": return {"error": 1}
    if uid in GAME["bets"]: return {"error": 2}
    if balance(uid) < amt: return {"error": 3}
    sub_balance(uid, amt)
    GAME["bets"][uid] = amt
    return {"ok": True}

@app.post("/cashout")
async def cashout(d: dict):
    uid = str(d["uid"])
    if GAME["state"] != "flying" or uid not in GAME["bets"]:
        return {"error": 1}
    win = round(GAME["bets"].pop(uid) * GAME["x"], 2)
    add_balance(uid, win)
    return {"win": win}

@app.get("/balance/{uid}")
def bal(uid: int):
    return {"balance": balance(uid)}

# ================== MINI APP ==================
@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{
 margin:0;
 background:radial-gradient(circle at top,#111827,#05070c);
 color:#fff;
 font-family:-apple-system,BlinkMacSystemFont,Arial;
}
#app{height:100vh;display:flex;flex-direction:column;justify-content:space-between;padding:16px}
.top{display:flex;justify-content:space-between}
.badge{background:#111827;padding:8px 16px;border-radius:20px;font-weight:600}
.center{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
.rocket{font-size:90px;transition:transform .12s linear;animation:idle 1.4s ease-in-out infinite}
@keyframes idle{0%{transform:translateY(0)}50%{transform:translateY(-6px)}100%{transform:translateY(0)}}
.flying{animation:fly .25s infinite alternate}
@keyframes fly{from{transform:translateY(0)}to{transform:translateY(-10px)}}
#x{font-size:54px;font-weight:800}
#timer{opacity:.6}
.controls{margin-bottom:90px}
input,button{
 width:100%;padding:16px;border-radius:18px;border:none;font-size:18px;margin-top:8px;
}
input{background:#0f172a;color:#60a5fa}
#bet{background:#2563eb;color:#fff}
#cash{background:#f59e0b;color:#000;display:none}
.bottom{
 position:fixed;bottom:0;left:0;right:0;
 background:#020617;display:flex;justify-content:space-around;
 padding:12px 0;font-weight:600
}
</style>
</head>
<body>
<div id="app">
 <div class="top">
  <div class="badge">👥 <span id="on"></span></div>
  <div class="badge">💰 <span id="bal"></span>$</div>
 </div>

 <div class="center">
  <div id="timer"></div>
  <div class="rocket" id="rocket">🚀</div>
  <div id="x">1.00x</div>
 </div>

 <div class="controls">
  <input id="amt" type="number" value="10">
  <button id="bet">Сделать ставку</button>
  <button id="cash"></button>
 </div>

 <div class="bottom">
  <div>🏆 Топ</div>
  <div>🚀 Краш</div>
  <div>👤 Профиль</div>
 </div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;
let last="", cashed=false;

async function tick(){
 let s = await fetch("/state").then(r=>r.json());
 let b = await fetch("/balance/"+uid).then(r=>r.json());

 on.innerText=s.online;
 bal.innerText=b.balance.toFixed(2);
 x.innerText=s.x.toFixed(2)+"x";
 timer.innerText=s.state==="waiting"?"Старт через "+s.timer+"с":"";

 if(s.state==="flying"){
  rocket.classList.add("flying");
  bet.style.display="none";
  if(s.bets[uid] && !cashed){
    cash.style.display="block";
    cash.innerText="Вывести "+(s.bets[uid]*s.x).toFixed(2)+"$";
  }
 }

 if(s.state==="waiting"){
  rocket.classList.remove("flying");
  rocket.innerText="🚀";
  bet.style.display="block";
  bet.disabled=false;
  cash.style.display="none";
  cashed=false;
 }

 if(s.state==="crashed" && last!=="crashed"){
  rocket.innerText="💥";
  cash.style.display="none";
  cashed=true;
 }
 last=s.state;
}
setInterval(tick,120);

bet.onclick=async()=>{
 bet.disabled=true;
 await fetch("/bet",{method:"POST",headers:{'Content-Type':'application/json'},
 body:JSON.stringify({uid:uid,amount:parseFloat(amt.value)})});
};

cash.onclick=async()=>{
 cashed=true;
 cash.style.display="none";
 await fetch("/cashout",{method:"POST",headers:{'Content-Type':'application/json'},
 body:JSON.stringify({uid:uid})});
};
</script>
</body>
</html>"""
