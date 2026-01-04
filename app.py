# --- ВЕСЬ PYTHON КОД БЕЗ ИЗМЕНЕНИЙ ---
# (он у тебя уже рабочий, я его не трогаю)

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
 background:#05070c;
 color:#fff;
 font-family:-apple-system,BlinkMacSystemFont,Arial;
 overflow:hidden;
}

#app{
 height:100vh;
 display:flex;
 flex-direction:column;
 justify-content:space-between;
 padding:16px;
}

.top{display:flex;justify-content:space-between}
.badge{background:#111827;padding:6px 14px;border-radius:20px}

.center{
 flex:1;
 display:flex;
 flex-direction:column;
 align-items:center;
 justify-content:center;
}

.rocket{
 font-size:96px;
 position:relative;
 transition:transform .12s linear;
 animation:idle 1.5s ease-in-out infinite;
}

@keyframes idle{
 0%{transform:translateY(0)}
 50%{transform:translateY(-6px)}
 100%{transform:translateY(0)}
}

.flying{
 animation:fly .25s infinite alternate;
}

@keyframes fly{
 from{transform:translateY(0) rotate(-1deg)}
 to{transform:translateY(-10px) rotate(1deg)}
}

.flame{
 position:absolute;
 bottom:-28px;
 left:50%;
 transform:translateX(-50%);
 font-size:26px;
 animation:flame .12s infinite alternate;
}

@keyframes flame{
 from{transform:translateX(-50%) scale(1)}
 to{transform:translateX(-50%) scale(1.4)}
}

#x{font-size:54px;font-weight:700}
#timer{opacity:.7}

.controls{margin-bottom:90px}
input,button{
 width:100%;
 padding:16px;
 border-radius:16px;
 border:none;
 font-size:18px;
 margin-top:8px;
}

#bet{background:#2563eb;color:#fff}
#bet:disabled{opacity:.5}

#cash{
 background:#f59e0b;
 color:#000;
 display:none;
}

.bottom{
 position:fixed;
 bottom:0;left:0;right:0;
 background:#0b0e14;
 display:flex;
 justify-content:space-around;
 padding:12px 0;
}
</style>
</head>

<body>
<div id="app">
 <div class="top">
  <div class="badge">👥 <span id="on"></span></div>
  <div class="badge">💰 <span id="bal"></span>$</div>
 </div>

 <div class="center">
  <div id="timer"></div>
  <div class="rocket" id="rocket">
    🚀
    <div class="flame">🔥</div>
  </div>
  <div id="x">1.00x</div>
 </div>

 <div class="controls">
  <input id="amt" type="number" value="10">
  <button id="bet">Сделать ставку</button>
  <button id="cash"></button>
 </div>

 <div class="bottom">
  <div>🏆 Топ</div>
  <div>🚀 Краш</div>
  <div>👤 Профиль</div>
 </div>
</div>

<script>
const tg = Telegram.WebApp; tg.expand();
const uid = tg.initDataUnsafe.user.id;

let lastState = "";
let cashedOut = false;

async function tick(){
 let s = await fetch("/state").then(r=>r.json());
 let b = await fetch("/balance/"+uid).then(r=>r.json());

 on.innerText = s.online;
 bal.innerText = b.balance.toFixed(2);
 x.innerText = s.x.toFixed(2)+"x";
 timer.innerText = s.state==="waiting" ? "Старт через "+s.timer+"с" : "";

 if(s.state==="flying"){
  rocket.classList.add("flying");
  rocket.style.transform="translateY(-"+(s.x*6)+"px)";
  bet.style.display="none";

  if(s.bets && s.bets[uid] && !cashedOut){
    cash.style.display="block";
    cash.innerText="Вывести "+(s.bets[uid]*s.x).toFixed(2)+"$";
  }
 }

 if(s.state==="waiting"){
  rocket.classList.remove("flying");
  rocket.style.transform="translateY(0)";
  rocket.innerText="🚀";
  bet.style.display="block";
  bet.disabled=false;
  cash.style.display="none";
  cashedOut = false;
 }

 if(s.state==="crashed" && lastState!=="crashed"){
  rocket.innerText="💥";
  cash.style.display="none";
  cashedOut = true;
 }

 lastState = s.state;
}

setInterval(tick,120);

bet.onclick = async ()=>{
 bet.disabled = true;
 cashedOut = false;
 await fetch("/bet",{
  method:"POST",
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({uid:uid,amount:parseFloat(amt.value)})
 });
};

cash.onclick = async ()=>{
 cashedOut = true;
 cash.style.display="none";
 await fetch("/cashout",{
  method:"POST",
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({uid:uid})
 });
};
</script>
</body>
</html>
"""
