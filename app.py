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
    "phase": "waiting",
    "timer": 5,
    "x": 1.00,
    "bets": {},
    "online": 0,
    "history": []
}

# ================= GAME LOOP =================
async def game_loop():
    while True:
        state["phase"] = "waiting"
        state["timer"] = 5
        state["x"] = 1.00
        state["bets"] = {}
        state["history"] = []
        state["online"] = random.randint(15, 60)

        for i in range(5, 0, -1):
            state["timer"] = i
            await asyncio.sleep(1)

        state["phase"] = "flying"
        crash_at = round(random.uniform(1.2, 6.0), 2)

        while state["x"] < crash_at:
            state["x"] = round(state["x"] + 0.01, 2)
            state["history"].append(state["x"])
            await asyncio.sleep(0.07)

        state["phase"] = "crashed"
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
        return {"balance": 0}
    return {"balance": float(r.data[0]["balance"])}

@app.post("/bet")
async def bet(data: dict):
    uid = str(data["uid"])
    amount = float(data["amount"])

    if state["phase"] != "waiting":
        return {"error": "round started"}

    bal = get_balance(uid)["balance"]
    if bal < amount:
        return {"error": "no money"}

    sb.table("balances").update({"balance": bal - amount}).eq("uid", uid).execute()
    state["bets"][uid] = amount
    return {"ok": True}

@app.post("/cashout")
async def cashout(data: dict):
    uid = str(data["uid"])
    if uid not in state["bets"]:
        return {"error": "no bet"}

    win = round(state["bets"][uid] * state["x"], 2)
    bal = get_balance(uid)["balance"]

    sb.table("balances").update({"balance": bal + win}).eq("uid", uid).execute()
    del state["bets"][uid]
    return {"win": win, "x": state["x"]}

@app.post("/admin/add")
async def admin_add(data: dict):
    if str(data["admin"]) != ADMIN_ID:
        return {"error": "forbidden"}

    uid = str(data["uid"])
    amount = float(data["amount"])
    bal = get_balance(uid)["balance"]

    sb.table("balances").update({"balance": bal + amount}).eq("uid", uid).execute()
    return {"ok": True}

# ================= UI =================
@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<title>Crash</title>
<style>
body{margin:0;background:#020617;color:#fff;font-family:Arial}
#app{padding:16px}
.rocket{font-size:100px;transition:1s}
.fly{transform:translate(200px,-200px)}
button,input{width:100%;padding:14px;margin-top:10px;border-radius:12px;border:none}
button{background:#2563eb;color:white}
#cash{background:#f59e0b;color:black;display:none}
#admin{display:none;margin-top:10px}
</style>
</head>
<body>

<div id="app">
<div>Онлайн: <span id="on"></span></div>
<div>Баланс: <span id="bal"></span>$</div>

<div style="text-align:center">
<div id="timer"></div>
<div class="rocket" id="rocket">🚀</div>
<div id="x">1.00x</div>
<div id="history"></div>
</div>

<input id="amt" type="number" value="10">
<button id="bet">Ставка</button>
<button id="cash"></button>

<button id="admin" onclick="admin()">АДМИН</button>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;
if(uid == '""" + ADMIN_ID + """') admin.style.display='block';

let last='';

async function tick(){
 const s = await fetch('/state').then(r=>r.json());
 const b = await fetch('/balance/'+uid).then(r=>r.json());

 on.innerText = s.online;
 bal.innerText = b.balance.toFixed(2);
 x.innerText = s.x.toFixed(2)+'x';
 history.innerText = s.history.slice(-10).join(' ');
 timer.innerText = s.phase=='waiting' ? 'Старт через '+s.timer : '';

 if(s.phase=='flying'){
   rocket.className='rocket fly';
   bet.style.display='none';
   if(s.bets[uid]){
     cash.style.display='block';
     cash.innerText='Вывести '+(s.bets[uid]*s.x).toFixed(2)+'$';
   }
 }

 if(s.phase=='waiting'){
   rocket.className='rocket';
   bet.style.display='block';
   cash.style.display='none';
 }

 last = s.phase;
}

setInterval(tick,120);

bet.onclick=()=>fetch('/bet',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid,amount:+amt.value})});
cash.onclick=()=>fetch('/cashout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid})});
function admin(){
 const u=prompt('UID'); const a=prompt('Сумма');
 fetch('/admin/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin:uid,uid:u,amount:a})});
}
</script>
</body>
</html>
""")
