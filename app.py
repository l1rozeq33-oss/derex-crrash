import os
import asyncio
import random
import sqlite3
from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
DOMAIN = os.getenv("DOMAIN")

MIN_BET = 0.5
MAX_BET = 20000

# ================== FASTAPI ==================
app = FastAPI()

# ================== DB ==================
conn = sqlite3.connect("casino.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)
""")
conn.commit()

def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (uid, 0))
        conn.commit()
        return 0
    return row[0]

def add_balance(uid, amount):
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    conn.commit()

def sub_balance(uid, amount):
    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, uid))
    conn.commit()

# ================== FAKE ONLINE ==================
def fake_online():
    return random.randint(37, 124)

# ================== UI ==================
def main_menu(balance):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Играть в Crash", callback_data="crash")],
        [InlineKeyboardButton(f"💰 Баланс: {balance:.2f}$", callback_data="balance")],
        [InlineKeyboardButton(f"👥 Онлайн: {fake_online()}", callback_data="noop")],
        [InlineKeyboardButton("👑 Админка", callback_data="admin")]
    ])

def bet_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("0.5$", callback_data="bet_0.5"),
            InlineKeyboardButton("1$", callback_data="bet_1"),
            InlineKeyboardButton("5$", callback_data="bet_5")
        ],
        [
            InlineKeyboardButton("10$", callback_data="bet_10"),
            InlineKeyboardButton("50$", callback_data="bet_50")
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ])

def cashout_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 КЭШ АУТ", callback_data="cashout")]
    ])

# ================== BOT ==================
application = Application.builder().token(BOT_TOKEN).build()

# хранение активных игр
active_games = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bal = get_balance(uid)
    await update.message.reply_text(
        "🚀 *DerexCrash*\n\n"
        "Поймай коэффициент до взрыва 💥\n"
        "Успей нажать *КЭШ АУТ*!",
        parse_mode="Markdown",
        reply_markup=main_menu(bal)
    )

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    bal = get_balance(uid)

    if q.data == "back":
        await q.edit_message_text("🏠 Главное меню", reply_markup=main_menu(bal))

    elif q.data == "crash":
        await q.edit_message_text("💸 Выбери сумму ставки", reply_markup=bet_menu())

    elif q.data.startswith("bet_"):
        bet = float(q.data.split("_")[1])

        if bet < MIN_BET or bet > MAX_BET:
            await q.answer("❌ Некорректная ставка", show_alert=True)
            return

        if bet > bal:
            await q.answer("❌ Недостаточно средств", show_alert=True)
            return

        sub_balance(uid, bet)
        await start_crash(q, uid, bet)

    elif q.data == "cashout":
        game = active_games.get(uid)
        if not game or game["ended"]:
            await q.answer("❌ Нельзя кэш-аут", show_alert=True)
            return

        game["ended"] = True
        win = game["bet"] * game["multiplier"]
        add_balance(uid, win)

        await game["message"].edit_text(
            f"💸 *КЭШ АУТ!*\n"
            f"Коэффициент: x{game['multiplier']:.2f}\n"
            f"Выигрыш: {win:.2f}$",
            parse_mode="Markdown",
            reply_markup=main_menu(get_balance(uid))
        )

    elif q.data == "admin":
        if uid != OWNER_ID:
            await q.answer("❌ Нет доступа", show_alert=True)
            return
        add_balance(uid, 100)
        await q.edit_message_text("👑 Админ: +100$ начислено")

# ================== CRASH ==================
async def start_crash(q, uid, bet):
    crash_point = round(random.uniform(1.6, 3.8), 2)
    multiplier = 1.0

    msg = await q.edit_message_text(
        "🚀 Ракета взлетает...\n`x1.00`",
        parse_mode="Markdown",
        reply_markup=cashout_menu()
    )

    active_games[uid] = {
        "bet": bet,
        "multiplier": multiplier,
        "crash": crash_point,
        "message": msg,
        "ended": False
    }

    while multiplier < crash_point:
        await asyncio.sleep(0.6)
        game = active_games.get(uid)
        if not game or game["ended"]:
            return

        multiplier += random.uniform(0.05, 0.15)
        game["multiplier"] = multiplier

        await msg.edit_text(
            f"🚀 Ракета летит...\n`x{multiplier:.2f}`",
            parse_mode="Markdown",
            reply_markup=cashout_menu()
        )

    game = active_games.get(uid)
    if game and not game["ended"]:
        game["ended"] = True
        await msg.edit_text(
            "💥 *БУМ!* Ракета взорвалась",
            parse_mode="Markdown",
            reply_markup=main_menu(get_balance(uid))
        )

# ================== WEBHOOK ==================
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    await application.process_update(Update.de_json(data, application.bot))
    return {"ok": True}

@app.on_event("startup")
async def startup():
    await application.initialize()
    await application.bot.set_webhook(f"{DOMAIN}/webhook")
    print("🤖 Bot started with webhook")

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callbacks))
