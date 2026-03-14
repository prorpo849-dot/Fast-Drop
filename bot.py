import os
import json
import time
import string
import random
import logging
import asyncio

from aiohttp import web
from aiohttp.web import middleware
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8657069014:AAECyVfbXP3ta9dWLi054uR_PC00F9Q1POY")
OWNER_ID = int(os.getenv("OWNER_ID", "6794644473"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== ХРАНЕНИЕ =====
balances = {}
gifts = {}
users = {}
vip_claimed = {}
promo_used = {}
daily_last = {}

# ===== НАСТРОЙКИ =====
VIP_IDS = ["6794644473", "6227572453", "6909040298"]
VIP_BONUS = 100000
DAILY_COOLDOWN = 24 * 60 * 60 * 1000

PROMO_CODES = {
    "FREE10": 10,
    "START50": 50
}


# ===== CORS =====
@middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        response = web.Response(status=200)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ===== ГЕНЕРАЦИЯ КОДА =====
def generate_code():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=6))


# ========================================
# API ЭНДПОИНТЫ
# ========================================

async def init_user(request):
    data = await request.json()
    user_id = str(data["user_id"])
    username = data.get("username")
    first_name = data.get("first_name")

    users[user_id] = {"username": username, "first_name": first_name}

    if user_id not in balances:
        balances[user_id] = 0

    vip_bonus = False
    vip_amount = 0

    if user_id in VIP_IDS and not vip_claimed.get(user_id):
        balances[user_id] += VIP_BONUS
        vip_claimed[user_id] = True
        vip_bonus = True
        vip_amount = VIP_BONUS

    return web.json_response({
        "ok": True,
        "balance": balances[user_id],
        "vip_bonus": vip_bonus,
        "vip_amount": vip_amount
    })


async def get_balance_new(request):
    user_id = str(request.match_info["user_id"])
    return web.json_response({
        "ok": True,
        "balance": balances.get(user_id, 0)
    })


async def get_balance(request):
    user_id = request.query.get("user_id")
    if not user_id:
        return web.json_response({"error": "no user id"})
    return web.json_response({
        "balance": balances.get(user_id, 0)
    })


async def set_balance(request):
    data = await request.json()
    user_id = str(data["user_id"])
    balance = int(data["balance"])
    balances[user_id] = balance
    return web.json_response({
        "ok": True,
        "balance": balances[user_id]
    })


async def change_balance(request):
    data = await request.json()
    user_id = str(data["user_id"])
    amount = int(data["amount"])
    current = balances.get(user_id, 0)

    if current + amount < 0:
        return web.json_response({
            "ok": False,
            "error": "Недостаточно средств"
        })

    balances[user_id] = current + amount
    return web.json_response({
        "ok": True,
        "balance": balances[user_id]
    })


async def add_balance(request):
    data = await request.json()
    user_id = str(data["user_id"])
    amount = int(data["amount"])
    balances[user_id] = balances.get(user_id, 0) + amount
    return web.json_response({
        "ok": True,
        "balance": balances[user_id]
    })


async def spend_balance(request):
    data = await request.json()
    user_id = str(data["user_id"])
    amount = int(data["amount"])
    balance = balances.get(user_id, 0)

    if balance < amount:
        return web.json_response({"ok": False, "error": "not enough stars"})

    balances[user_id] = balance - amount
    return web.json_response({
        "ok": True,
        "balance": balances[user_id]
    })


async def save_gift(request):
    data = await request.json()
    user_id = str(data["user_id"])
    gift = data.get("gift")

    if not gift:
        code = generate_code()
        gift = {
            "code": code,
            "name": data.get("prize_name", ""),
            "img": data.get("prize_img", ""),
            "stars": data.get("prize_stars", 0),
            "caseName": data.get("case_name", ""),
            "date": time.strftime("%d.%m.%Y, %H:%M:%S")
        }
    else:
        code = gift.get("code", generate_code())
        gift["code"] = code

    if user_id not in gifts:
        gifts[user_id] = []
    gifts[user_id].append(gift)

    user_data = users.get(user_id, {})
    username = user_data.get("username")
    first_name = user_data.get("first_name", "Гость")
    display_name = f"@{username}" if username else first_name

    try:
        await bot.send_message(
            OWNER_ID,
            f"🎁 Новый выигрыш!\n\n"
            f"👤 {display_name}\n"
            f"🆔 {user_id}\n\n"
            f"📦 {gift.get('caseName', '')}\n"
            f"🏆 {gift['name']}\n"
            f"⭐️ {gift.get('stars', 0)}\n\n"
            f"🔑 {code}\n"
            f"🕐 {gift.get('date', '')}"
        )
    except Exception as e:
        logging.error(f"Notify error: {e}")

    return web.json_response({
        "ok": True,
        "code": code,
        "date": gift.get("date", "")
    })


async def get_gifts(request):
    user_id = str(request.match_info["user_id"])
    return web.json_response({
        "ok": True,
        "gifts": gifts.get(user_id, [])
    })


async def sell_gift(request):
    data = await request.json()
    user_id = str(data["user_id"])
    code = data["code"]
    user_gifts = gifts.get(user_id, [])

    gift = None
    for g in user_gifts:
        if g["code"] == code:
            gift = g
            break

    if not gift:
        return web.json_response({"ok": False, "error": "Подарок не найден"})

    user_gifts.remove(gift)
    gifts[user_id] = user_gifts
    balances[user_id] = balances.get(user_id, 0) + gift.get("stars", 0)

    return web.json_response({
        "ok": True,
        "balance": balances[user_id]
    })


async def vip_check(request):
    user_id = str(request.match_info["user_id"])
    return web.json_response({
        "ok": True,
        "claimed": vip_claimed.get(user_id, False)
    })


async def vip_claim(request):
    data = await request.json()
    user_id = str(data["user_id"])
    vip_claimed[user_id] = True
    return web.json_response({"ok": True})


async def daily_check(request):
    user_id = str(request.match_info["user_id"])
    last = daily_last.get(user_id, 0)
    now = int(time.time() * 1000)
    diff = DAILY_COOLDOWN - (now - last)
    return web.json_response({
        "ok": True,
        "timeLeft": diff if diff > 0 else 0
    })


async def daily_claim(request):
    data = await request.json()
    user_id = str(data["user_id"])
    now = int(time.time() * 1000)
    last = daily_last.get(user_id, 0)
    diff = DAILY_COOLDOWN - (now - last)

    if diff > 0:
        return web.json_response({
            "ok": False,
            "error": "Ещё не время",
            "timeLeft": diff
        })

    daily_last[user_id] = now
    return web.json_response({"ok": True})


async def activate_promo(request):
    data = await request.json()
    user_id = str(data["user_id"])
    code = data["code"].strip().upper()

    reward = PROMO_CODES.get(code)
    if not reward:
        return web.json_response({"error": "invalid"})

    if user_id not in promo_used:
        promo_used[user_id] = set()

    if code in promo_used[user_id]:
        return web.json_response({"error": "already_used"})

    promo_used[user_id].add(code)
    balances[user_id] = balances.get(user_id, 0) + reward

    return web.json_response({
        "success": True,
        "reward": reward,
        "balance": balances[user_id]
    })


# ===== БОТ =====

@dp.message(Command("start"))
async def start(message: types.Message):
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("buy_"):
        amount = int(args[1].replace("buy_", ""))
        await send_invoice(message.chat.id, amount)
    else:
        await message.answer(
            "👋 Привет!\n\nЭто бот FastDrop для покупки ⭐️"
        )


async def send_invoice(chat_id, amount):
    await bot.send_invoice(
        chat_id=chat_id,
        title=f"⭐️ {amount} звёзд FastDrop",
        description=f"Покупка {amount} звёзд для открытия кейсов",
        payload=json.dumps({"amount": amount, "chat_id": chat_id}),
        currency="XTR",
        prices=[types.LabeledPrice(label=f"{amount} звёзд", amount=amount)]
    )


@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)


@dp.message()
async def successful_payment(message: types.Message):
    if message.successful_payment:
        payload = json.loads(message.successful_payment.invoice_payload)
        amount = payload["amount"]
        user = message.from_user
        user_id = str(user.id)
        username = f"@{user.username}" if user.username else user.first_name

        balances[user_id] = balances.get(user_id, 0) + amount

        await bot.send_message(
            OWNER_ID,
            f"💰 Новая оплата\n\n👤 {username}\n🆔 {user.id}\n⭐ {amount}"
        )

        await message.answer(
            f"✅ Оплата прошла!\n\n⭐ Начислено {amount} звёзд."
        )


# ===== WEBHOOK =====

async def webhook_handler(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")


# ===== ЗАПУСК =====

async def main():
    webhook_url = os.getenv("WEBHOOK_URL")
    port = int(os.getenv("PORT", 8080))

    app = web.Application(middlewares=[cors_middleware])

    # Бот
    app.router.add_post("/webhook", webhook_handler)

    # Старые
    app.router.add_get("/balance", get_balance)
    app.router.add_post("/add_balance", add_balance)
    app.router.add_post("/spend_balance", spend_balance)

    # Новые
    app.router.add_post("/api/init", init_user)
    app.router.add_get("/api/balance/{user_id}", get_balance_new)
    app.router.add_post("/api/balance", set_balance)
    app.router.add_post("/api/balance/change", change_balance)
    app.router.add_post("/api/gifts", save_gift)
    app.router.add_get("/api/gifts/{user_id}", get_gifts)
    app.router.add_post("/api/gifts/sell", sell_gift)
    app.router.add_get("/api/vip-check/{user_id}", vip_check)
    app.router.add_post("/api/vip-claim", vip_claim)
    app.router.add_get("/api/daily/{user_id}", daily_check)
    app.router.add_post("/api/daily/claim", daily_claim)
    app.router.add_post("/api/promo", activate_promo)

    if webhook_url:
        await bot.set_webhook(f"{webhook_url}/webhook")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logging.info(f"✅ Сервер на порту {port}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
