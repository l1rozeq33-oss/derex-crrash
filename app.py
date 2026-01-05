import json
import random
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

ADMIN_ID = "123456789"  # <<< ВСТАВЬ СЮДА СВОЙ TG ID

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
history = load(HIST_FILE, {})

state = {
    "state": "waiting",
    "timer": 5,
    "x": 1.00,
    "bets": {},
    "online": random.randint(10, 40)
}

# ================= GAME LOOP =================
async def game_loop():
    while True:
        state.update({
            "state": "waiting",
            "timer": 5,
            "bets": {},
            "x": 1.00,
            "online": random.randint(10, 40)
        })

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
    asyncio.create_task(game_loop())

# ================= API =================
@app.get("/state")
def get_state():
    return state

@app.get("/balance/{uid}")
def get_balance(uid: str):
    if uid not in balances:
        balances[uid] = 0.0
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
        return {"error": "no access"}
    uid = str(data["uid"])
    amt = float(data["amount"])
    balances[uid] = balances.get(uid, 0) + amt
    save(BAL_FILE, balances)
    return {"ok": True}

# ================= MINI APP =================
@app.get("/", response_class=HTMLResponse)
def index():
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://telegram.org/js/telegram-web-app.js"></script>

<style>
body {{
 background:#020617;
 color:white;
 font-family:Arial;
 margin:0;
 overflow:hidden;
}}
.rocket {{
 font-size:110px;
 transition:transform 0.8s ease, opacity 0.8s ease;
}}
.fly {{
 transform:translate(280px,-320px) rotate(45deg);
 opacity:0;
}}
.menu {{
 display:flex;
 justify-content:space-around;
 padding:20px;
}}
button,input {{
 width:100%;
 padding:16px;
 border-radius:14px;
 margin-top:8px;
 border:none;
 font-size:18px;
}}
#popup {{
 position:fixed;
 top:20px;
 left:50%;
 transform:translateX(-50%);
 background:#020617;
 border:1px solid #22c55e;
 padding:14px 22px;
 border-radius:16px;
 display:none;
}}
</style>
</head>

<body>
<div id="popup"></div>

<div id="app">
<div id="rocket" class="rocket">🚀</div>
<div id="x">1.00x</div>

<input id="amt" type="number" value="10">
<button id="bet">Сделать ставку</button>
<button id="cash" style="display:none;background:#f59e0b">Вывести</button>

<div class="menu">
 <div onclick="openAdmin()">⚙ Админка</div>
</div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;
const ADMIN_ID = "{ADMIN_ID}";
let crashed=false;

function popup(t) {{
 let p=document.getElementById("popup");
 p.innerText=t;
 p.style.display="block";
 setTimeout(()=>p.style.display="none",2500);
}}

async function tick(){{
 let s=await fetch("/state").then(r=>r.json());
 let r=document.getElementById("rocket");

 document.getElementById("x").innerText=s.x.toFixed(2)+"x";

 if(s.state==="flying"){{
  crashed=false;
  r.classList.remove("fly");
  r.style.transform="translateY(-"+(s.x*6)+"px)";
 }}

 if(s.state==="crashed" && !crashed){{
  crashed=true;
  r.classList.add("fly");
 }}

 if(s.state==="waiting"){{
  r.classList.remove("fly");
  r.style.transform="translateY(0)";
 }}
}}

setInterval(tick,120);

bet.onclick=()=>fetch("/bet",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{uid,amount:+amt.value}})}});

cash.onclick=async()=>{{
 let r=await fetch("/cashout",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{uid}})}}).then(r=>r.json());
 popup("+"+r.win+"$");
}}

function openAdmin(){{
 if(uid!=ADMIN_ID) return;
 let u=prompt("ID");
 let a=prompt("Сумма");
 fetch("/admin/add",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{admin:uid,uid:u,amount:a}})}})
}}
</script>
</body>
</html>
"""
