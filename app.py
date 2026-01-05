from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import threading, time, random, sqlite3

app = FastAPI()

# ================== DATABASE ==================

conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    balance INTEGER
)
""")
conn.commit()

def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE id=?", (uid,))
    r = cur.fetchone()
    if r is None:
        cur.execute("INSERT INTO users VALUES (?,?)", (uid, 1000))
        conn.commit()
        return 1000
    return r[0]

def set_balance(uid, bal):
    cur.execute("UPDATE users SET balance=? WHERE id=?", (bal, uid))
    conn.commit()

# ================== GAME STATE ==================

state = {
    "mult": 1.0,
    "flying": False,
    "crashed": False,
    "history": [],
}

bets = {}        # user -> bet
locked = set()  # защита от спама

# ================== GAME LOOP ==================

def game_loop():
    while True:
        state["mult"] = 1.0
        state["flying"] = True
        state["crashed"] = False
        crash = random.uniform(1.7, 6.5)

        while state["mult"] < crash:
            time.sleep(0.1)
            state["mult"] += 0.05

        state["crashed"] = True
        state["flying"] = False
        state["history"].insert(0, round(state["mult"], 2))
        state["history"] = state["history"][:12]
        bets.clear()
        locked.clear()
        time.sleep(3)

threading.Thread(target=game_loop, daemon=True).start()

# ================== API ==================

@app.get("/state")
def get_state():
    return state

@app.get("/balance/{u}")
def bal(u: str):
    return {"balance": get_balance(u)}

@app.post("/bet/{u}/{a}")
def bet(u: str, a: int):
    if u in locked or state["flying"]:
        return {"ok": False}
    bal = get_balance(u)
    if a <= 0 or a > bal:
        return {"ok": False}

    locked.add(u)
    set_balance(u, bal - a)
    bets[u] = a
    return {"ok": True}

@app.post("/cashout/{u}")
def cashout(u: str):
    if u not in bets or state["crashed"]:
        return {"ok": False}

    win = int(bets[u] * state["mult"])
    set_balance(u, get_balance(u) + win)
    del bets[u]
    return {"ok": True, "win": win}

# ================== ADMIN ==================

@app.get("/admin")
def admin():
    return {
        "bets": bets,
        "state": state
    }

# ================== FRONT ==================

@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Crash</title>
<style>
body{margin:0;background:#0b0f1a;color:#fff;font-family:Arial}
.top{display:flex;justify-content:space-between;padding:15px;background:#111}
.box{background:#161b2e;padding:15px;border-radius:10px}
#game{height:320px;position:relative;overflow:hidden}
#rocket{position:absolute;font-size:42px;left:10px;bottom:10px}
button{padding:10px 18px;border:0;border-radius:8px;background:#3b82f6;color:#fff;font-size:16px}
button:disabled{opacity:.4}
</style>
</head>
<body>

<div class="top">
 <div class="box">Баланс: <span id="bal">0</span> 💰</div>
 <div class="box">CRASH</div>
</div>

<div class="box" style="margin:15px">
 <h1 id="mult">1.00x</h1>
 <div id="game">
   <div id="rocket">🚀</div>
 </div>
 <div id="hist"></div>
</div>

<div class="box" style="margin:15px">
 <input id="amt" type="number" value="100">
 <button id="bet">Ставка</button>
 <button id="out" style="display:none">Вывести</button>
</div>

<script>
let u="user1", locked=false;

async function upd(){
 let s=await fetch("/state").then(r=>r.json());
 document.getElementById("mult").innerText=s.mult.toFixed(2)+"x";
 document.getElementById("hist").innerHTML=s.history.map(x=>x+"x").join(" ");

 let r=document.getElementById("rocket");
 if(s.flying){
   r.style.left=(s.mult*40)+"px";
   r.style.bottom=(s.mult*15)+"px";
 }else{
   r.style.left="10px";r.style.bottom="10px";
   document.getElementById("out").style.display="none";
   locked=false;
 }
}
setInterval(upd,100);

async function bal(){
 let b=await fetch("/balance/"+u).then(r=>r.json());
 document.getElementById("bal").innerText=b.balance;
}
bal();

document.getElementById("bet").onclick=async()=>{
 if(locked) return;
 locked=true;
 let a=document.getElementById("amt").value;
 let r=await fetch("/bet/"+u+"/"+a,{method:"POST"}).then(r=>r.json());
 if(r.ok) document.getElementById("out").style.display="inline";
 bal();
};

document.getElementById("out").onclick=async()=>{
 document.getElementById("out").style.display="none";
 await fetch("/cashout/"+u,{method:"POST"});
 bal();
};
</script>

</body>
</html>
"""
