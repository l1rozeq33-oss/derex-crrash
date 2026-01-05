import json, random, asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

ADMIN_ID = "7963516753"

app = FastAPI()

BAL_FILE = "balances.json"
HIST_FILE = "history.json"

def load(p, d):
    try:
        with open(p) as f: return json.load(f)
    except: return d

def save(p, d):
    with open(p,"w") as f: json.dump(d,f)

balances = load(BAL_FILE,{})
history = load(HIST_FILE,{})

state = {
    "state":"waiting",
    "timer":5,
    "x":1.00,
    "bets":{},
    "online":random.randint(10,40)
}

# ================= GAME LOOP =================
async def game():
    while True:
        state.update({
            "state":"waiting",
            "timer":5,
            "x":1.00,
            "bets":{},
            "online":random.randint(10,40)
        })
        for i in range(5,0,-1):
            state["timer"]=i
            await asyncio.sleep(1)

        state["state"]="flying"
        crash = random.choice(
            [round(random.uniform(1.0,1.3),2)]*4 +
            [round(random.uniform(1.5,4.5),2)]
        )
        while state["x"] < crash:
            state["x"]=round(state["x"]+0.01,2)
            await asyncio.sleep(0.12)

        state["state"]="crashed"
        for u,b in list(state["bets"].items()):
            history.setdefault(u,[]).append({
                "bet":b,"result":"crash","x":state["x"]
            })
        save(HIST_FILE,history)
        await asyncio.sleep(2)

@app.on_event("startup")
async def start():
    asyncio.create_task(game())

# ================= API =================
@app.get("/state")
def s(): return state

@app.get("/balance/{u}")
def bal(u:str):
    if u not in balances:
        balances[u] = 0.0   # <<< ИЗНАЧАЛЬНО 0$
        save(BAL_FILE,balances)
    return {"balance":balances[u]}

@app.post("/bet")
async def bet(d:dict):
    u=str(d["uid"])
    a=float(d["amount"])
    if state["state"]!="waiting": return {"error":"round"}
    if u in state["bets"]: return {"error":"already"}
    if balances.get(u,0)<a: return {"error":"money"}
    balances[u]-=a
    state["bets"][u]=a
    save(BAL_FILE,balances)
    return {"ok":1}

@app.post("/cashout")
async def cash(d:dict):
    u=str(d["uid"])
    if u not in state["bets"]: return {"error":1}
    win=round(state["bets"][u]*state["x"],2)
    balances[u]+=win
    history.setdefault(u,[]).append({
        "bet":state["bets"][u],"result":"win","x":state["x"]
    })
    del state["bets"][u]
    save(BAL_FILE,balances)
    save(HIST_FILE,history)
    return {"win":win,"x":state["x"]}

@app.get("/history/{u}")
def h(u:str): return history.get(u,[])

@app.post("/admin/add")
async def admin(d:dict):
    if d["admin"]!=ADMIN_ID: return {"error":1}
    u=str(d["uid"])
    balances[u]=balances.get(u,0)+float(d["amount"])
    save(BAL_FILE,balances)
    return {"ok":1}

# ================= MINI APP =================
@app.get("/",response_class=HTMLResponse)
def index():
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta name=viewport content="width=device-width,initial-scale=1,user-scalable=no">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
body{{margin:0;background:radial-gradient(circle at top,#020617,#000);color:#fff;font-family:Arial;overflow:hidden}}
#app{{padding:16px;height:100vh;display:flex;flex-direction:column;justify-content:space-between}}
.badge{{background:#020617cc;padding:10px 18px;border-radius:20px}}
.center{{text-align:center}}
.rocket{{font-size:120px;transition:.12s}}
input,button{{width:100%;padding:18px;border-radius:18px;border:none;font-size:20px;margin-top:10px}}
input{{background:#0f172a;color:#38bdf8}}
button{{background:#2563eb;color:white}}
#cash{{background:#f59e0b;color:black;display:none}}
.menu{{display:flex;justify-content:space-around;background:#020617;padding:20px;margin-bottom:40px;border-radius:30px}}
.popup{{position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#020617;padding:16px 24px;border-radius:20px;display:none;animation:fade .3s}}
@keyframes fade{{from{{opacity:0;transform:translate(-50%,-10px)}}to{{opacity:1}}}}
.admin{{display:none}}
</style>
</head>
<body>
<div class=popup id=popup></div>
<div id=app>
<div style="display:flex;justify-content:space-between">
<div class=badge>👥 <span id=on></span></div>
<div class=badge>💰 <span id=bal></span>$</div>
</div>

<div class=center>
<div id=timer></div>
<div class=rocket id=rocket>🚀</div>
<div id=x>1.00x</div>
</div>

<div>
<input id=amt type=number value=10 inputmode=numeric>
<button id=bet>Сделать ставку</button>
<button id=cash></button>
</div>

<div class=menu>
<div onclick="msg('Пополнение временно недоступно. @DerexSupport')">➕ Пополнить</div>
<div onclick="showHist()">📜 История</div>
<div onclick="msg('Вывод временно недоступен. @DerexSupport')">💸 Вывести</div>
</div>

<div class=admin id=admin>
<input id=au placeholder="TG ID">
<input id=aa placeholder="Сумма">
<button onclick="give()">Начислить</button>
<button onclick="admin.style.display='none'">Назад</button>
</div>

</div>

<script>
const tg=Telegram.WebApp;tg.expand()
const uid=tg.initDataUnsafe.user.id
if(uid=="{ADMIN_ID}") admin.style.display="block"
let cashed=false

function msg(t){{popup.innerText=t;popup.style.display="block";setTimeout(()=>popup.style.display="none",2500)}}

async function tick(){{
let s=await fetch("/state").then(r=>r.json())
let b=await fetch("/balance/"+uid).then(r=>r.json())
on.innerText=s.online
bal.innerText=b.balance.toFixed(2)
x.innerText=s.x.toFixed(2)+"x"
timer.innerText=s.state=="waiting"?"Старт через "+s.timer:""

if(s.state=="flying"){{
rocket.style.transform="translateY(-"+(s.x*5)+"px)"
bet.style.display="none"
if(s.bets && s.bets[uid] && !cashed){{
cash.style.display="block"
cash.innerText="Вывести "+(s.bets[uid]*s.x).toFixed(2)+"$"
}}}}

if(s.state=="waiting"){{
rocket.style.transform="translateY(0)"
bet.style.display="block"
cash.style.display="none"
cashed=false
}}

if(s.state=="crashed"){{
rocket.innerText="💥"
cash.style.display="none"
cashed=true
}}
}}
setInterval(tick,120)

bet.onclick=()=>fetch("/bet",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{uid,amount:+amt.value}})}})
cash.onclick=async()=>{{
cashed=true;cash.style.display="none"
let r=await fetch("/cashout",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{uid}})}}).then(r=>r.json())
msg("Вы выиграли "+r.win+"$ | x"+r.x)
}}

async function showHist(){{
let h=await fetch("/history/"+uid).then(r=>r.json())
msg(h.slice(-5).reverse().map(i=>(i.result=="win"?"🟢":"🔴")+" "+i.bet+"$ x"+i.x).join("\\n"))
}}

async function give(){{
await fetch("/admin/add",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{admin:"{ADMIN_ID}",uid:au.value,amount:aa.value}})}})
msg("Начислено")
}}
</script>
</body>
</html>
"""
