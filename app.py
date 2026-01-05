import os
import random
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from supabase import create_client

ADMIN_ID = "7963516753"

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

state = {
    "state": "waiting",
    "timer": 5,
    "x": 1.00,
    "bets": {},
    "online": 0,
    "history_x": []
}

# ================= GAME LOOP =================
async def game_loop():
    while True:
        state["state"] = "waiting"
        state["timer"] = 5
        state["x"] = 1.00
        state["bets"] = {}
        state["history_x"] = []
        state["online"] = random.randint(12, 48)

        for i in range(5, 0, -1):
            state["timer"] = i
            await asyncio.sleep(1)

        state["state"] = "flying"
        crash_at = random.choice(
            [round(random.uniform(1.0, 1.3), 2)] * 4 +
            [round(random.uniform(1.5, 5.0), 2)]
        )

        while state["x"] < crash_at:
            state["x"] = round(state["x"] + 0.01, 2)
            state["history_x"].append(state["x"])
            await asyncio.sleep(0.08)

        state["state"] = "crashed"
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup():
    asyncio.create_task(game_loop())

# ================= API =================
@app.get("/state")
def get_state():
    return state

@app.get("/balance/{uid}")
def get_balance(uid: str):
    r = sb.table("balances").select("balance").eq("uid", uid).execute()
    if not r.data:
        sb.table("balances").insert({"uid": uid, "balance": 0}).execute()
        return {"balance": 0.0}
    return {"balance": float(r.data[0]["balance"])}

@app.post("/bet")
async def bet(data: dict):
    uid = str(data["uid"])
    amt = float(data["amount"])

    if state["state"] != "waiting":
        return {"error": "round started"}
    if uid in state["bets"]:
        return {"error": "already bet"}

    bal = get_balance(uid)["balance"]
    if bal < amt:
        return {"error": "no money"}

    sb.table("balances").update({"balance": bal - amt}).eq("uid", uid).execute()
    state["bets"][uid] = amt
    return {"ok": True}

@app.post("/cashout")
async def cashout(data: dict):
    uid = str(data["uid"])
    if uid not in state["bets"]:
        return {"error": "no bet"}

    win = round(state["bets"][uid] * state["x"], 2)
    bal = get_balance(uid)["balance"]

    sb.table("balances").update({"balance": bal + win}).eq("uid", uid).execute()
    sb.table("history").insert({
        "uid": uid,
        "bet": state["bets"][uid],
        "result": "win",
        "x": state["x"]
    }).execute()

    del state["bets"][uid]
    return {"win": win, "x": state["x"]}

@app.post("/admin/add")
async def admin_add(data: dict):
    if str(data["admin"]) != ADMIN_ID:
        return {"error": "forbidden"}

    uid = str(data["uid"])
    amt = float(data["amount"])
    bal = get_balance(uid)["balance"]

    sb.table("balances").update({"balance": bal + amt}).eq("uid", uid).execute()
    return {"ok": True}

# ================= MINI APP =================
@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<title>Derex Crash</title>

<style>
body {{
 margin:0;
 background:radial-gradient(circle at top,#020617,#000);
 color:#fff;
 font-family:Arial;
 overflow:hidden;
}}
#app{{padding:16px;height:100vh;display:flex;flex-direction:column;justify-content:space-between}}
.badge{{background:#020617;padding:8px 14px;border-radius:20px;font-size:14px}}
.center{{text-align:center}}
.rocket{{font-size:120px;transition:transform .12s linear}}
input,button{{width:100%;padding:18px;border-radius:16px;border:none;font-size:20px;margin-top:10px}}
input{{background:#020617;color:#38bdf8}}
button{{background:#2563eb;color:white}}
#cash{{background:#f59e0b;color:black;display:none}}
.menu{{display:flex;justify-content:space-around;background:#020617;padding:16px;margin-bottom:20px;border-radius:20px}}
#history{{font-size:12px;opacity:.6;margin-top:6px;min-height:14px}}
#admin{{display:none}}
</style>
</head>

<body>
<div id="app">
 <div style="display:flex;justify-content:space-between">
  <div class="badge">👥 <span id="on">0</span></div>
  <div class="badge">💰 <span id="bal">0.00</span></div>
 </div>

 <div class="center">
  <div id="timer"></div>
  <div class="rocket" id="rocket">🚀</div>
  <div id="x">1.00x</div>
  <div id="history"></div>
 </div>

 <div>
  <input id="amt" type="number" value="10">
  <button id="bet">Сделать ставку</button>
  <button id="cash"></button>
 </div>

 <div class="menu">
  <div onclick="alert('Пополнение временно недоступно')">➕ Пополнить</div>
  <div>🚀 Краш</div>
  <div onclick="alert('Вывод временно недоступен')">💸 Вывести</div>
  <div id="admin" onclick="admin()">👑 Админ</div>
 </div>
</div>

<script>
const tg = Telegram.WebApp;
tg.expand();

const uid = String(tg.initDataUnsafe.user.id);
const ADMIN_ID = "{ADMIN_ID}";
if(uid === ADMIN_ID) document.getElementById("admin").style.display="block";

let cashed=false, last="";
let rocketY = 0;

async function tick(){
 let s = await fetch("/state").then(r=>r.json());
 let b = await fetch("/balance/"+uid).then(r=>r.json());

 document.getElementById("on").innerText = s.online;
 document.getElementById("bal").innerText = b.balance.toFixed(2);
 document.getElementById("x").innerText = s.x.toFixed(2)+"x";
 document.getElementById("history").innerText = s.history_x.slice(-14).join(" ");
 document.getElementById("timer").innerText =
   s.state=="waiting" ? "Старт через "+s.timer : "";

 if(s.state=="flying"){
  rocketY -= 2;
  document.getElementById("rocket").style.transform =
    "translateY("+rocketY+"px)";
  document.getElementById("bet").style.display="none";

  if(s.bets[uid] && !cashed){
    let c = document.getElementById("cash");
    c.style.display="block";
    c.innerText="Вывести "+(s.bets[uid]*s.x).toFixed(2)+"$";
  }
 }

 if(s.state=="crashed" && last!="crashed"){
  cashed=true;
  document.getElementById("cash").style.display="none";
 }

 if(s.state=="waiting"){
  rocketY = 0;
  document.getElementById("rocket").style.transform="translateY(0)";
  document.getElementById("bet").style.display="block";
  document.getElementById("cash").style.display="none";
  cashed=false;
 }

 last = s.state;
}

setInterval(tick,120);

document.getElementById("bet").onclick=()=>{
 fetch("/bet",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({uid:uid,amount:+amt.value})
 });
};

document.getElementById("cash").onclick=async ()=>{
 cashed=true;
 let r = await fetch("/cashout",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({uid:uid})
 }).then(r=>r.json());
 alert("+"+r.win+"$ | x"+r.x);
};

function admin(){
 let u = prompt("UID");
 let a = prompt("Сумма");
 fetch("/admin/add",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({admin:uid,uid:u,amount:a})
 });
}
</script>
</body>
</html>
""")
