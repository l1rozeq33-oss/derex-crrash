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

# ================== BALANCE (FOREVER) ==================
BAL_FILE = "balances.json"

def load_bal():
    if not os.path.exists(BAL_FILE):
        return {}
    return json.load(open(BAL_FILE))

def save_bal(b):
    json.dump(b, open(BAL_FILE,"w"))

balances = load_bal()

def balance(uid): return float(balances.get(str(uid),0))
def add_balance(uid,a):
    balances[str(uid)] = balance(uid)+a
    save_bal(balances)
def sub_balance(uid,a):
    balances[str(uid)] = balance(uid)-a
    save_bal(balances)

# ================== BOT ==================
bot = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb=[[InlineKeyboardButton("🚀 Играть",web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text("🎰 DEREX CASINO",reply_markup=InlineKeyboardMarkup(kb))

async def give(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID: return
    uid,amt=ctx.args
    add_balance(uid,float(amt))
    await update.message.reply_text("✅ Баланс выдан")

bot.add_handler(CommandHandler("start",start))
bot.add_handler(CommandHandler("give",give))

# ================== GAME ==================
GAME={
 "state":"waiting",
 "x":1.0,
 "crash":1.0,
 "bets":{},
 "history":[],
 "online":random.randint(25,70),
 "timer":5
}

GLOBAL_HISTORY=[]  # история выводов

def gen_crash():
    r=random.random()
    if r<0.25:return 1.00
    if r<0.45:return 1.30
    return round(random.uniform(1.5,6),2)

async def game_loop():
    while True:
        GAME["state"]="waiting"
        GAME["bets"]={}
        GAME["x"]=1.0
        for i in range(5,0,-1):
            GAME["timer"]=i
            await asyncio.sleep(1)

        GAME["state"]="flying"
        GAME["crash"]=gen_crash()

        while GAME["x"]<GAME["crash"]:
            GAME["x"]=round(GAME["x"]+0.01,2)
            await asyncio.sleep(0.12)

        GAME["state"]="crashed"
        GAME["history"].insert(0,GAME["crash"])
        GAME["history"]=GAME["history"][:10]
        await asyncio.sleep(0.6)

# ================== API ==================
@app.on_event("startup")
async def startup():
    await bot.initialize()
    await bot.bot.set_webhook(WEBAPP_URL+"/webhook")
    asyncio.create_task(game_loop())

@app.post("/webhook")
async def webhook(req:Request):
    data=await req.json()
    await bot.process_update(Update.de_json(data,bot.bot))
    return {"ok":True}

@app.get("/state")
def state(): return GAME

@app.get("/history")
def hist(): return GLOBAL_HISTORY[-10:]

@app.post("/bet")
async def bet(d:dict):
    uid=str(d["uid"])
    amt=float(d["amount"])
    if GAME["state"]!="waiting": return {"error":1}
    if uid in GAME["bets"]: return {"error":2}
    if balance(uid)<amt: return {"error":3}
    sub_balance(uid,amt)
    GAME["bets"][uid]=amt
    return {"ok":True}

@app.post("/cashout")
async def cashout(d:dict):
    uid=str(d["uid"])
    if GAME["state"]!="flying" or uid not in GAME["bets"]:
        return {"error":1}
    win=round(GAME["bets"].pop(uid)*GAME["x"],2)
    add_balance(uid,win)
    GLOBAL_HISTORY.append({
        "uid":uid,
        "win":win,
        "x":round(GAME["x"],2)
    })
    return {"win":win,"x":GAME["x"]}

@app.get("/balance/{uid}")
def bal(uid:int): return {"balance":balance(uid)}

# ================== MINI APP ==================
@app.get("/",response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html>
<head>
<meta name=viewport content="width=device-width,initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{margin:0;background:#05070c;color:#fff;font-family:Arial}
#app{height:100vh;display:flex;flex-direction:column;padding:16px}
.badge{background:#111827;padding:8px 16px;border-radius:20px}
.center{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
.rocket{font-size:90px;transition:.12s;animation:idle 1.4s infinite}
@keyframes idle{50%{transform:translateY(-6px)}}
.flying{animation:fly .25s infinite alternate}
@keyframes fly{to{transform:translateY(-10px)}}
input,button{width:100%;padding:16px;border-radius:18px;border:none;margin-top:8px}
input{background:#0f172a;color:#60a5fa}
#bet{background:#2563eb;color:#fff}
#cash{background:#f59e0b;color:#000;display:none}
.popup{
 position:fixed;top:40%;left:50%;transform:translate(-50%,-50%);
 background:#111827;padding:24px;border-radius:20px;
 display:none;text-align:center
}
.bottom{display:flex;justify-content:space-around;padding:12px;background:#020617}
.hist{font-size:14px;opacity:.8}
</style>
</head>
<body>
<div id=app>
 <div style="display:flex;justify-content:space-between">
  <div class=badge>👥 <span id=on></span></div>
  <div class=badge>💰 <span id=bal></span>$</div>
 </div>

 <div class=center>
  <div id=timer></div>
  <div id=rocket class=rocket>🚀</div>
  <div id=x>1.00x</div>
 </div>

 <input id=amt type=number value=10>
 <button id=bet>Сделать ставку</button>
 <button id=cash></button>

 <div class=hist id=hist></div>

 <div class=bottom>
  <div onclick="showProfile()">👤 Профиль</div>
 </div>
</div>

<div class=popup id=popup></div>

<script>
const tg=Telegram.WebApp;tg.expand();
const uid=tg.initDataUnsafe.user.id;
let last="",cashed=false;

async function tick(){
 let s=await fetch("/state").then(r=>r.json());
 let b=await fetch("/balance/"+uid).then(r=>r.json());
 let h=await fetch("/history").then(r=>r.json());

 on.innerText=s.online;
 bal.innerText=b.balance.toFixed(2);
 x.innerText=s.x.toFixed(2)+"x";
 timer.innerText=s.state==="waiting"?"Старт через "+s.timer+"с":"";
 hist.innerHTML=h.map(e=>`👤 ${e.uid} | +${e.win}$ (${e.x}x)`).join("<br>");

 if(s.state==="flying"){
  rocket.classList.add("flying");
  bet.style.display="none";
  if(s.bets[uid]&&!cashed){
   cash.style.display="block";
   cash.innerText="Вывести "+(s.bets[uid]*s.x).toFixed(2)+"$";
  }
 }

 if(s.state==="waiting"){
  rocket.classList.remove("flying");
  rocket.innerText="🚀";
  bet.style.display="block";
  cash.style.display="none";
  cashed=false;
 }

 if(s.state==="crashed"&&last!=="crashed"){
  rocket.innerText="💥";
  cash.style.display="none";
 }
 last=s.state;
}

setInterval(tick,120);

bet.onclick=()=>fetch("/bet",{method:"POST",headers:{'Content-Type':'application/json'},
body:JSON.stringify({uid,amount:+amt.value})});

cash.onclick=async()=>{
 cashed=true;
 let r=await fetch("/cashout",{method:"POST",headers:{'Content-Type':'application/json'},
 body:JSON.stringify({uid})}).then(r=>r.json());
 popup.style.display="block";
 popup.innerHTML="💰 Вывод<br><b>"+r.win+"$</b><br>("+r.x+"x)";
 setTimeout(()=>popup.style.display="none",2500);
 cash.style.display="none";
};

function showProfile(){
 alert("Ваш ID: "+uid);
}
</script>
</body>
</html>"""
