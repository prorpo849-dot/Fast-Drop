import logging
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice
import json
import os

# ===== Змінні середовища =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
FASTDROP_API = os.environ.get("FASTDROP_API")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== Функція нарахування зірок =====
async def add_stars(user_id: int, amount: int):
    url = f"{FASTDROP_API}/api/user/tg_{user_id}/balance"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                logging.error(f"Ошибка при получении баланса: {resp.status}")
                return
            data = await resp.json()
            balance = data.get("balance", 0)

        new_balance = balance + amount

        async with session.post(url, json={"balance": new_balance}) as resp:
            if resp.status != 200:
                logging.error(f"Ошибка при обновлении баланса: {resp.status}")
                return
            return await resp.json()

# ===== /start =====
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Привет!\nЯ бот FastDrop для покупки ⭐️ звёзд.\n"
        "Используй команду /buy <кол-во>, чтобы купить звёзды вручную.\n"
        "Пример: /buy 100"
    )

# ===== /buy =====
@dp.message(Command("buy"))
async def buy_command(message: types.Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Пожалуйста, укажи количество звёзд. Пример: /buy 100")
        return
    amount = int(args[1])
    await send_invoice(message.chat.id, amount)

# ===== Відправка інвойсу =====
async def send_invoice(chat_id: int, amount: int):
    await bot.send_invoice(
        chat_id=chat_id,
        title=f"⭐️ {amount} звёзд FastDrop",
        description=f"Покупка {amount} звёзд для открытия кейсов в FastDrop",
        payload=json.dumps({"amount": amount, "chat_id": chat_id}),
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} звёзд", amount=amount)]
    )

# ===== Перевірка перед оплатою =====
@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

# ===== Успішна оплата =====
@dp.message(lambda m: m.successful_payment)
async def successful_payment(message: types.Message):
    payload = json.loads(message.successful_payment.invoice_payload)
    amount = payload["amount"]
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    logging.info(f"Payment: {user.id} bought {amount} stars")

    await add_stars(user.id, amount)

    # Уведомление владельцу
    await bot.send_message(
        OWNER_ID,
        f"💰 Новая покупка!\n\n"
        f"👤 {username}\n"
        f"🆔 ID: {user.id}\n"
        f"⭐ Куплено: {amount}\n"
        f"⚡ Начислено вручную"
    )

    # Уведомление пользователю
    await message.answer(f"✅ Оплата прошла успешно!\n⭐️ {amount} звёзд зачислены на ваш баланс FastDrop!")

# ===== Webhook (опционально) =====
async def webhook(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")

# ===== Main =====
async def main():
    webhook_url = os.environ.get("WEBHOOK_URL", "")
    port = int(os.environ.get("PORT", 8080))

    if webhook_url:
        logging.info("Running in webhook mode")
        await bot.set_webhook(f"{webhook_url}/webhook")
        app = web.Application()
        app.router.add_post("/webhook", webhook)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        await asyncio.Event().wait()
    else:
        logging.info("Running in polling mode")
        await bot.delete_webhook()
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
