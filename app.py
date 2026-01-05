import json
import random
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

ADMIN_ID = "7963516753"

app = FastAPI()

BAL_FILE = "balances.json"
HIST_FILE = "history.json"

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
history = load(HIST_FILE, {"rounds": []})

state = {
    "state": "waiting",
    "timer": 5,
    "x": 1.00,
    "bets": {},
    "online": random.randint(10, 40),
    "round_history": history.get("rounds", [])
}

# ================= GAME LOOP =================
async def game_loop():
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

        # ===== СОХРАНЯЕМ ФИНАЛЬНЫЙ ИКС =====
        state["round_history"].insert(0, state["x"])
        state["round_history"] = state["round_history"][:15]
        history["rounds"] = state["round_history"]
        save(HIST_FILE, history)

        await asyncio.sleep(2)

@app.on_event("startup")
async def startup():
    asyncio.get_event_loop().create_task(game_loop())

# ================= API =================
@app.get("/state")
def get_state():
    return state

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
    del state["bets"][uid]

    save(BAL_FILE, balances)
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
body{
 margin:0;
 background:radial-gradient(circle at top,#1e293b,#020617);
 color:#fff;
 font-family:Arial;
 overflow:hidden;
}
#app{padding:16px;height:100vh;display:flex;flex-direction:column;justify-content:space-between}
.badge{background:#020617;padding:8px 16px;border-radius:20px}
.center{text-align:center}
.rocket{font-size:110px;transition:transform .9s cubic-bezier(.4,1.6,.6,1),opacity .9s}
.flyaway{transform:translate(240px,-260px) rotate(45deg);opacity:0}
#hx{font-size:13px;opacity:.7;margin-top:6px}
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
  <div class="rocket" id="rocket">🚀</div>
  <div id="x">1.00x</div>
  <div id="hx"></div>
 </div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;

async function tick(){
 const s = await fetch("/state").then(r=>r.json());
 const b = await fetch("/balance/"+uid).then(r=>r.json());

 on.innerText=s.online;
 bal.innerText=b.balance.toFixed(2);
 x.innerText=s.x.toFixed(2)+"x";
 hx.innerText = s.round_history.map(v=>v.toFixed(2)+"x").join("  ");
 timer.innerText=s.state=="waiting"?"Старт через "+s.timer:"";

 if(s.state=="crashed") rocket.classList.add("flyaway");
 if(s.state=="waiting") rocket.classList.remove("flyaway");
}

setInterval(tick,120);
</script>
</body>
</html>
"""
    return HTMLResponse(html.replace("__ADMIN__", ADMIN_ID))
