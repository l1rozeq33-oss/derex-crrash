import os, asyncio, random, sqlite3, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBAPP_URL = os.getenv("WEBAPP_URL")

app = FastAPI()

# ---------- DATABASE ----------
db = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance REAL)")
db.commit()

def balance(uid):
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users VALUES (?,0)", (uid,))
        db.commit()
        return 0
    return r[0]

def set_balance(uid, val):
    cur.execute("UPDATE users SET balance=? WHERE id=?", (val, uid))
    db.commit()

# ---------- BOT ----------
bot = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🚀 Играть в Crash", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        "🎰 DEREX CASINO\n\nCrash Game",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def give(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(ctx.args[0])
    amt = float(ctx.args[1])
    set_balance(uid, balance(uid) + amt)
    await update.message.reply_text(f"✅ Выдано {amt}$ пользователю {uid}")

bot.add_handler(CommandHandler("start", start))
bot.add_handler(CommandHandler("give", give))

# ---------- GAME ----------
GAME = {
    "state": "waiting",
    "x": 1.0,
    "crash": 0,
    "bets": {},
    "online": random.randint(15, 35),
    "history": [],
    "start_at": time.time()
}

async def game_loop():
    while True:
        GAME["state"] = "waiting"
        GAME["bets"] = {}
        GAME["start_at"] = time.time() + 5
        await asyncio.sleep(5)

        GAME["state"] = "flying"
        GAME["crash"] = round(random.uniform(1.3, 7), 2)
        GAME["x"] = 1.0

        while GAME["x"] < GAME["crash"]:
            GAME["x"] = round(GAME["x"] + 0.02, 2)
            await asyncio.sleep(0.12)

        GAME["state"] = "crashed"
        GAME["history"].insert(0, GAME["crash"])
        GAME["history"] = GAME["history"][:10]
        await asyncio.sleep(5)

# ---------- FASTAPI ----------
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
    if GAME["state"] != "waiting":
        return {"error": 1}
    if balance(uid) < amt:
        return {"error": 2}
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

# ---------- MINI APP ----------
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
 background:radial-gradient(circle at top,#14182a,#0b0e14);
 color:#fff;
 font-family:Arial
}
#app{
 height:100vh;
 display:flex;
 flex-direction:column;
 align-items:center;
 justify-content:center;
 text-align:center
}
#panel{
 width:92%;
 max-width:420px;
 background:#12162a;
 border-radius:24px;
 padding:22px;
 box-shadow:0 0 40px rgba(0,0,0,.6)
}
#rocket{font-size:110px;transition:transform .12s}
#x{font-size:76px;font-weight:900;margin:10px}
#timer{font-size:22px;opacity:.7;margin-bottom:6px}
#top{margin-bottom:10px}
input,button{
 width:100%;
 padding:18px;
 font-size:22px;
 border-radius:18px;
 border:none;
 margin-top:10px
}
#bet{background:#1c2036;color:#fff}
#bet:disabled{opacity:.4}
#cash{
 background:#ff8c1a;
 color:#000;
 font-weight:900;
 display:none
}
#hist{margin-top:12px}
#hist span{margin:0 5px;opacity:.7}
</style>
</head>
<body>
<div id="app">
<div id="panel">
<div id="top">
<div>💰 Баланс: <span id="bal">0</span>$</div>
<div>👥 Online: <span id="on"></span></div>
</div>

<div id="timer"></div>
<div id="rocket">🚀</div>
<div id="x">1.00x</div>

<input id="amt" type="number" min="1" value="10">
<button id="bet">СДЕЛАТЬ СТАВКУ</button>
<button id="cash"></button>

<div id="hist"></div>
</div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;

let lastState="";
let betAmount=0;

async function tick(){
 let s = await fetch("/state").then(r=>r.json());
 x.innerText = s.x.toFixed(2)+"x";
 on.innerText = s.online;
 hist.innerHTML = s.history.map(h=>"<span>"+h+"x</span>").join("");

 let b = await fetch("/balance/"+uid).then(r=>r.json());
 bal.innerText = b.balance.toFixed(2);

 if(s.state==="waiting"){
  let t = Math.max(0, Math.ceil(s.start_at - Date.now()/1000));
  timer.innerText = "Старт через " + t + " сек";
  rocket.style.transform="translateY(0)";
  bet.disabled=false;
  bet.style.display="block";
  cash.style.display="none";
  betAmount=0;
 }

 if(s.state==="flying"){
  timer.innerText="";
  rocket.style.transform="translateY(-"+(s.x*9)+"px)";
  bet.disabled=true;
  bet.style.display="none";
  if(betAmount>0){
    cash.style.display="block";
    cash.innerText="ВЫВЕСТИ "+(betAmount*s.x).toFixed(2)+"$";
  }
 }

 if(s.state==="crashed" && lastState!=="crashed"){
  rocket.innerText="💥";
  setTimeout(()=>rocket.innerText="🚀",1000);
 }

 lastState=s.state;
}

setInterval(tick,160);

bet.onclick = async ()=>{
 let a = parseFloat(amt.value);
 let r = await fetch("/bet",{
   method:"POST",
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({uid:uid,amount:a})
 });
 let j = await r.json();
 if(j.ok) betAmount=a;
};

cash.onclick = async ()=>{
 await fetch("/cashout",{
   method:"POST",
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({uid:uid})
 });
 cash.style.display="none";
};
</script>
</body>
</html>
"""
