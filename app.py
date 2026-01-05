import os, asyncio, random, sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

app = FastAPI()

# ================== DATABASE ==================
db = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL)")
db.commit()

def balance(uid: int) -> float:
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users VALUES (?,0)", (uid,))
        db.commit()
        return 0.0
    return r[0]

def set_balance(uid: int, val: float):
    cur.execute("UPDATE users SET balance=? WHERE id=?", (val, uid))
    db.commit()

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
    set_balance(uid, balance(uid) + amt)
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
    if balance(uid) < amt: return {"error": 2}
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

# ================== MINI APP ==================
@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{margin:0;background:#05070c;color:#fff;font-family:-apple-system,BlinkMacSystemFont,Arial}
#app{height:100vh;display:flex;flex-direction:column;justify-content:space-between;padding:16px}
.top{display:flex;justify-content:space-between}
.badge{background:#111827;padding:6px 14px;border-radius:20px}
.center{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
.rocket{font-size:96px;position:relative;transition:transform .12s linear;animation:idle 1.5s infinite}
@keyframes idle{0%{transform:translateY(0)}50%{transform:translateY(-6px)}100%{transform:translateY(0)}}
.flying{animation:fly .25s infinite alternate}
@keyframes fly{from{transform:translateY(0)}to{transform:translateY(-10px)}}
.flame{position:absolute;bottom:-28px;left:50%;transform:translateX(-50%);font-size:26px;animation:flame .12s infinite alternate}
@keyframes flame{from{transform:translateX(-50%) scale(1)}to{transform:translateX(-50%) scale(1.4)}}
#x{font-size:54px;font-weight:700}
#timer{opacity:.7}
.controls{margin-bottom:90px}
input,button{width:100%;padding:16px;border-radius:16px;border:none;font-size:18px;margin-top:8px}
#bet{background:#2563eb;color:#fff}
#bet:disabled{opacity:.5}
#cash{background:#f59e0b;color:#000;display:none}
.bottom{position:fixed;bottom:0;left:0;right:0;background:#0b0e14;display:flex;justify-content:space-around;padding:12px 0}
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
 <div class="rocket" id="rocket">🚀<div class="flame">🔥</div></div>
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
let lastState="", cashed=false;

async function tick(){
 let s = await fetch("/state").then(r=>r.json());
 let b = await fetch("/balance/"+uid).then(r=>r.json());
 on.innerText=s.online;
 bal.innerText=b.balance.toFixed(2);
 x.innerText=s.x.toFixed(2)+"x";
 timer.innerText=s.state==="waiting" ? "Старт через "+s.timer+"с" : "";

 if(s.state==="flying"){
  rocket.classList.add("flying");
  bet.style.display="none";
  if(s.bets && s.bets[uid] && !cashed){
    cash.style.display="block";
    cash.innerText="Вывести "+(s.bets[uid]*s.x).toFixed(2)+"$";
  }
 }

 if(s.state==="waiting"){
  rocket.classList.remove("flying");
  bet.style.display="block";
  bet.disabled=false;
  cash.style.display="none";
  cashed=false;
 }

 if(s.state==="crashed" && lastState!=="crashed"){
  rocket.innerText="💥";
  cash.style.display="none";
  cashed=true;
  setTimeout(()=>rocket.innerHTML="🚀<div class='flame'>🔥</div>",300);
 }

 lastState=s.state;
}
setInterval(tick,120);

bet.onclick=async ()=>{
 bet.disabled=true;
 cashed=false;
 await fetch("/bet",{method:"POST",headers:{'Content-Type':'application/json'},
 body:JSON.stringify({uid:uid,amount:parseFloat(amt.value)})});
};

cash.onclick=async ()=>{
 cashed=true;
 cash.style.display="none";
 await fetch("/cashout",{method:"POST",headers:{'Content-Type':'application/json'},
 body:JSON.stringify({uid:uid})});
};
</script>
</body>
</html>
"""
