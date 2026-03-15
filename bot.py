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


# ===== START =====
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


# ===== ОТПРАВКА ИНВОЙСА =====
async def send_invoice(chat_id: int, amount: int):
    await bot.send_invoice(
        chat_id=chat_id,
        title=f"⭐️ {amount} звёзд FastDrop",
        description=f"Покупка {amount} звёзд для открытия кейсов в FastDrop",
        payload=json.dumps({
            "amount": amount,
            "chat_id": chat_id
        }),
        currency="XTR",
        prices=[
            types.LabeledPrice(
                label=f"{amount} звёзд",
                amount=amount
            )
        ]
    )


# ===== ПРОВЕРКА ПЕРЕД ОПЛАТОЙ =====
@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)


# ===== УСПЕШНАЯ ОПЛАТА =====
@dp.message(lambda message: message.successful_payment)
async def successful_payment(message: types.Message):

    payload = json.loads(message.successful_payment.invoice_payload)
    amount = payload["amount"]

    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    logging.info(f"Payment: {user.id} bought {amount} stars")

    # уведомление владельцу
    await bot.send_message(
        OWNER_ID,
        f"✅ Оплата получена!\n\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: {user.id}\n"
        f"⭐️ Куплено: {amount} звёзд"
    )

    # уведомление пользователю
    await message.answer(
        f"✅ Оплата прошла успешно!\n\n"
        f"⭐️ {amount} звёзд будут начислены в течение нескольких минут.\n\n"
        f"Спасибо за покупку! 🎁"
    )


# ===== WEBHOOK HANDLER =====
async def webhook(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")


# ===== MAIN =====
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
