import os
import json
import logging
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

BOT_TOKEN = "8657069014:AAFy7rJ2ymZFPxmBzpFW6WNvheHLW0pm8Kg"
OWNER_ID = 6794644473

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== БД (JSON файл) =====
DB_FILE = "db.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(db, uid):
    uid = str(uid)
    if uid not in db:
        db[uid] = {"balance": 0, "gifts": [], "flags": {}}
    return db[uid]


# ===== CORS MIDDLEWARE =====
@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ===== API ROUTES =====

# GET /users/{uid}/balance
async def get_balance(request):
    uid = request.match_info["uid"]
    db = load_db()
    user = get_user(db, uid)
    return web.json_response({"balance": user["balance"]})

# POST /users/{uid}/balance
async def set_balance(request):
    uid = request.match_info["uid"]
    data = await request.json()
    db = load_db()
    user = get_user(db, uid)
    user["balance"] = data["balance"]
    save_db(db)
    return web.json_response({"ok": True})

# GET /users/{uid}/gifts
async def get_gifts(request):
    uid = request.match_info["uid"]
    db = load_db()
    user = get_user(db, uid)
    return web.json_response({"gifts": user["gifts"]})

# POST /users/{uid}/gifts  — добавить подарок
async def add_gift(request):
    uid = request.match_info["uid"]
    data = await request.json()
    db = load_db()
    user = get_user(db, uid)
    user["gifts"].append(data)
    save_db(db)
    return web.json_response({"ok": True})

# POST /users/{uid}/gifts/delete
async def delete_gift(request):
    uid = request.match_info["uid"]
    data = await request.json()
    code = data["code"]
    db = load_db()
    user = get_user(db, uid)
    user["gifts"] = [g for g in user["gifts"] if g["code"] != code]
    save_db(db)
    return web.json_response({"ok": True})

# GET /users/{uid}/flags
async def get_flags(request):
    uid = request.match_info["uid"]
    db = load_db()
    user = get_user(db, uid)
    return web.json_response(user["flags"])

# POST /users/{uid}/flags
async def set_flag(request):
    uid = request.match_info["uid"]
    data = await request.json()
    db = load_db()
    user = get_user(db, uid)
    user["flags"][data["key"]] = data["value"]
    save_db(db)
    return web.json_response({"ok": True})

# POST /users/{uid}/balance/add  — начислить звёзды после оплаты
async def add_balance(request):
    uid = request.match_info["uid"]
    data = await request.json()
    amount = data.get("amount", 0)
    db = load_db()
    user = get_user(db, uid)
    user["balance"] += amount
    save_db(db)
    return web.json_response({"ok": True, "balance": user["balance"]})


# ===== TELEGRAM BOT HANDLERS =====

@dp.message(Command("start"))
async def start(message: types.Message):
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("buy_"):
        try:
            amount = int(args[1].replace("buy_", ""))
        except ValueError:
            await message.answer("❌ Неверное количество звёзд")
            return
        await send_invoice(message.chat.id, amount)
    else:
        await message.answer(
            "👋 Привет!\n\n"
            "Я бот FastDrop для покупки ⭐️ звёзд.\n"
            "После оплаты звёзды будут начислены в приложение."
        )

async def send_invoice(chat_id: int, amount: int):
    await bot.send_invoice(
        chat_id=chat_id,
        title=f"⭐️ {amount} звёзд FastDrop",
        description=f"Покупка {amount} звёзд для открытия кейсов в FastDrop",
        payload=json.dumps({"amount": amount, "chat_id": chat_id}),
        currency="XTR",
        prices=[types.LabeledPrice(label=f"{amount} звёзд", amount=amount)]
    )

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(lambda message: message.successful_payment)
async def successful_payment(message: types.Message):
    payload = json.loads(message.successful_payment.invoice_payload)
    amount = payload["amount"]
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    # Начисляем баланс напрямую в БД
    db = load_db()
    db_user = get_user(db, str(user.id))
    db_user["balance"] += amount
    save_db(db)

    logging.info(f"Payment: {user.id} bought {amount} stars, new balance: {db_user['balance']}")

    await bot.send_message(
        OWNER_ID,
        f"✅ Оплата получена!\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: {user.id}\n"
        f"⭐️ Куплено: {amount} звёзд\n"
        f"💰 Новый баланс: {db_user['balance']} ⭐️"
    )

    await message.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"⭐️ {amount} звёзд начислено на ваш баланс!\n\n"
        f"Спасибо за покупку! 🎁"
    )


# ===== WEBHOOK =====
async def webhook(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")


# ===== MAIN =====
async def main():
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    port = int(os.environ.get("PORT", 8080))

    app = web.Application(middlewares=[cors_middleware])

    # Telegram webhook
    app.router.add_post("/webhook", webhook)

    # API routes
    app.router.add_get("/users/{uid}/balance", get_balance)
    app.router.add_post("/users/{uid}/balance", set_balance)
    app.router.add_post("/users/{uid}/balance/add", add_balance)
    app.router.add_get("/users/{uid}/gifts", get_gifts)
    app.router.add_post("/users/{uid}/gifts", add_gift)
    app.router.add_post("/users/{uid}/gifts/delete", delete_gift)
    app.router.add_get("/users/{uid}/flags", get_flags)
    app.router.add_post("/users/{uid}/flags", set_flag)

    # OPTIONS для CORS preflight
    for path in [
        "/users/{uid}/balance",
        "/users/{uid}/balance/add",
        "/users/{uid}/gifts",
        "/users/{uid}/gifts/delete",
        "/users/{uid}/flags",
    ]:
        app.router.add_route("OPTIONS", path, lambda r: web.Response())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    if webhook_url:
        logging.info(f"Webhook mode: {webhook_url}")
        await bot.set_webhook(f"{webhook_url}/webhook")
    else:
        logging.info("Polling mode")
        await bot.delete_webhook()
        asyncio.create_task(dp.start_polling(bot))

    logging.info(f"Server started on port {port}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
