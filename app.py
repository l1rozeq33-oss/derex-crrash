import json
import random
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

ADMIN_ID = "7963516753"

app = FastAPI()

BAL_FILE = "balances.json"
HIST_FILE = "history.json"
ROUND_FILE = "rounds.json"

def load(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

balances = load(BAL_FILE, {})
history = load(HIST_FILE, {})
round_history = load(ROUND_FILE, [])

state = {
    "state": "waiting",
    "timer": 5,
    "x": 1.00,
    "bets": {},
    "online": random.randint(10, 40)
}

# ================= GAME LOOP =================
async def game_loop():
    global round_history
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

        round_history.insert(0, state["x"])
        round_history = round_history[:10]
        save(ROUND_FILE, round_history)

        for uid, bet in list(state["bets"].items()):
            history.setdefault(uid, []).append({
                "bet": bet,
                "result": "crash",
                "x": state["x"]
            })

        save(HIST_FILE, history)
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup():
    asyncio.get_event_loop().create_task(game_loop())

# ================= API =================
@app.get("/state")
def get_state():
    return {**state, "rounds": round_history}

@app.get("/balance/{uid}")
def get_balance(uid: str):
    balances.setdefault(uid, 0)
    save(BAL_FILE, balances)
    return {"balance": balances[uid]}

@app.post("/bet")
async def bet(data: dict):
    uid = str(data["uid"])
    amt = float(data["amount"])

    if state["state"] != "waiting":
        return {"error": "round started"}

    if uid in state["bets"]:
        return {"error": "already bet"}

    if balances.get(uid, 0) < amt:
        return {"error": "no money"}

    balances[uid] -= amt
    state["bets"][uid] = amt
    save(BAL_FILE, balances)
    return {"ok": True}

@app.post("/cashout")
async def cashout(data: dict):
    uid = str(data["uid"])

    if uid not in state["bets"]:
        return {"error": "no bet"}

    win = round(state["bets"][uid] * state["x"], 2)
    balances[uid] += win

    history.setdefault(uid, []).append({
        "bet": state["bets"][uid],
        "result": "win",
        "x": state["x"]
    })

    del state["bets"][uid]
    save(BAL_FILE, balances)
    save(HIST_FILE, history)

    return {"win": win, "x": state["x"]}

@app.post("/admin/add")
async def admin_add(data: dict):
    if str(data["admin"]) != ADMIN_ID:
        return {"error": "forbidden"}

    uid = str(data["uid"])
    amt = float(data["amount"])
    balances[uid] = balances.get(uid, 0) + amt
    save(BAL_FILE, balances)
    return {"ok": True}

# ================= MINI APP =================
@app.get("/", response_class=HTMLResponse)
def index():
    html = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<title>DerexCasino</title>
<style>
body{margin:0;background:#020617;color:#fff;font-family:Arial}
#app{padding:16px;height:100vh;display:flex;flex-direction:column;justify-content:space-between}
.badge{background:#020617;padding:8px 16px;border-radius:20px}
.center{text-align:center}
.rocket{font-size:110px}
.history{margin-top:10px;font-size:14px;opacity:.8}
.history span{margin-right:6px}
</style>
</head>
<body>
<div id="app">
 <div style="display:flex;justify-content:space-between">
  <div class="badge">👥 <span id="on"></span></div>
  <div class="badge">💰 <span id="bal"></span>$</div>
 </div>

 <div class="center">
  <div id="timer"></div>
  <div class="rocket">🚀</div>
  <div id="x">1.00x</div>
  <div class="history" id="hist"></div>
 </div>

 <div>
  <input id="amt" type="number" value="10">
  <button id="bet">Сделать ставку</button>
  <button id="cash" style="display:none"></button>
 </div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;

async function tick(){
 let s=await fetch("/state").then(r=>r.json());
 let b=await fetch("/balance/"+uid).then(r=>r.json());

 on.innerText=s.online;
 bal.innerText=b.balance.toFixed(2);
 x.innerText=s.x.toFixed(2)+"x";
 timer.innerText=s.state=="waiting"?"Старт через "+s.timer:"";

 hist.innerHTML="";
 s.rounds.forEach(v=>{
  let sp=document.createElement("span");
  sp.innerText=v.toFixed(2)+"x";
  hist.appendChild(sp);
 });
}
setInterval(tick,120);

bet.onclick=()=>fetch("/bet",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify({uid,amount:+amt.value})});
cash.onclick=()=>fetch("/cashout",{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify({uid})});
</script>
</body>
</html>
"""
    return HTMLResponse(html)
