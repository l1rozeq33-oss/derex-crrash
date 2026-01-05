import json
import os
import random
import time
import threading
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

DATA_FILE = "data.json"
ADMIN_TG_ID = 123456789  # <-- ВСТАВЬ СЮДА СВОЙ TG ID

# -------------------- STORAGE --------------------

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "history": []}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()

# -------------------- GAME STATE --------------------

game = {
    "running": False,
    "multiplier": 1.0,
    "crash_at": 0,
    "start_time": 0
}

def game_loop():
    while True:
        game["running"] = True
        game["multiplier"] = 1.0
        game["crash_at"] = round(random.uniform(1.5, 6.0), 2)
        game["start_time"] = time.time()

        while game["running"]:
            elapsed = time.time() - game["start_time"]
            game["multiplier"] = round(1 + elapsed * 0.6, 2)
            if game["multiplier"] >= game["crash_at"]:
                game["running"] = False
                data["history"].insert(0, game["crash_at"])
                data["history"] = data["history"][:10]
                save_data(data)
                break
            time.sleep(0.1)

        time.sleep(3)

threading.Thread(target=game_loop, daemon=True).start()

# -------------------- API --------------------

@app.get("/state")
def state():
    return {
        "running": game["running"],
        "multiplier": game["multiplier"],
        "history": data["history"]
    }

@app.get("/balance/{user_id}")
def balance(user_id: str):
    if user_id not in data["users"]:
        data["users"][user_id] = {"balance": 0}
        save_data(data)
    return {"balance": data["users"][user_id]["balance"]}

@app.post("/bet/{user_id}")
def bet(user_id: str):
    if user_id not in data["users"]:
        data["users"][user_id] = {"balance": 0}
    if data["users"][user_id]["balance"] <= 0:
        return {"error": "no money"}
    return {"ok": True}

@app.get("/admin/{tg_id}")
def admin(tg_id: int):
    if tg_id != ADMIN_TG_ID:
        return {"error": "forbidden"}
    return data

# -------------------- UI --------------------

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Crash</title>
<style>
body {
    margin: 0;
    background: radial-gradient(circle at top, #1b1f3b, #0b0e1a);
    color: white;
    font-family: Arial, sans-serif;
    text-align: center;
}
#mult {
    font-size: 64px;
    margin-top: 80px;
}
#history {
    margin-top: 20px;
    opacity: 0.8;
}
.buttons {
    position: fixed;
    bottom: 60px;
    width: 100%;
}
button {
    padding: 12px 20px;
    margin: 5px;
    font-size: 16px;
    border-radius: 8px;
    border: none;
}
</style>
</head>
<body>

<div id="mult">1.00x</div>
<div id="history"></div>

<div class="buttons">
    <button onclick="deposit()">Пополнить</button>
    <button onclick="cashout()" id="cashoutBtn">Вывести</button>
    <button>Crash</button>
</div>

<script>
let cashed = false;

async function update() {
    const s = await fetch("/state").then(r => r.json());

    document.getElementById("mult").innerText =
        s.running ? s.multiplier.toFixed(2) + "x" : "CRASH";

    document.getElementById("history").innerText =
        "History: " + s.history.join(" | ");

    if (!s.running) {
        cashed = false;
        document.getElementById("cashoutBtn").style.display = "inline-block";
    }
}

function cashout() {
    if (cashed) return;
    cashed = true;
    document.getElementById("cashoutBtn").style.display = "none";
    alert("Автоматический вывод временно недоступен. Support Derex.");
}

function deposit() {
    alert("Автоматическое пополнение временно недоступно. Support Derex.");
}

setInterval(update, 300);
</script>

</body>
</html>
"""
