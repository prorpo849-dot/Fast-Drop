import os
import json
import time
import string
import random
import logging
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8657069014:AAECyVfbXP3ta9dWLi054uR_PC00F9Q1POY"  # ← вставьте токен бота от @BotFather
OWNER_ID = 6794644473

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== ХРАНЕНИЕ БАЛАНСОВ =====
balances = {}

# ===== API =====

async def get_balance(request):
    user_id = request.query.get("user_id")

    if not user_id:
        return web.json_response({"error": "no user id"})

    balance = balances.get(user_id, 0)

    return web.json_response({
        "balance": balance
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


# ===== БОТ =====

@dp.message(Command("start"))
async def start(message: types.Message):

    args = message.text.split()

    if len(args) > 1 and args[1].startswith("buy_"):

        amount = int(args[1].replace("buy_", ""))

        await send_invoice(message.chat.id, amount)

    else:

        await message.answer(
            "👋 Привет!\n\n"
            "Это бот FastDrop для покупки ⭐️"
        )


async def send_invoice(chat_id, amount):

    await bot.send_invoice(
        chat_id=chat_id,
        title=f"⭐️ {amount} звёзд FastDrop",
        description=f"Покупка {amount} звёзд для открытия кейсов",
        payload=json.dumps({
            "amount": amount,
            "chat_id": chat_id
        }),
        currency="XTR",
        prices=[types.LabeledPrice(label=f"{amount} звёзд", amount=amount)]
    )


@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)


@dp.message()
async def successful_payment(message: types.Message):

    if message.successful_payment:

        payload = json.loads(
            message.successful_payment.invoice_payload
        )

        amount = payload["amount"]

        user = message.from_user
        user_id = str(user.id)

        username = (
            f"@{user.username}"
            if user.username
            else user.first_name
        )

        # начисляем звезды
        balances[user_id] = balances.get(user_id, 0) + amount

        # уведомление владельцу
        await bot.send_message(
            OWNER_ID,
            f"💰 Новая оплата\n\n"
            f"👤 {username}\n"
            f"🆔 {user.id}\n"
            f"⭐ {amount}"
        )

        # уведомление пользователю
        await message.answer(
            f"✅ Оплата прошла успешно!\n\n"
            f"⭐ Вам начислено {amount} звёзд."
        )


# ===== WEBHOOK =====

async def webhook(request):

    data = await request.json()

    update = types.Update(**data)

    await dp.feed_update(bot, update)

    return web.Response(text="ok")


# ===== SERVER =====

async def main():

    webhook_url = os.getenv("WEBHOOK_URL")
    port = int(os.getenv("PORT", 8080))

    app = web.Application()

    app.router.add_post("/webhook", webhook)

    app.router.add_get("/balance", get_balance)
    app.router.add_post("/add_balance", add_balance)
    app.router.add_post("/spend_balance", spend_balance)

    await bot.set_webhook(f"{webhook_url}/webhook")

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", port)

    await site.start()

    import asyncio
    await asyncio.Event().wait()


if __name__ == "__main__":

    import asyncio

    asyncio.run(main())
