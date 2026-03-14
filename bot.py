import os
import json
import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice

# ===== Конфигурация =====
BOT_TOKEN = "8657069014:AAECyVfbXP3ta9dWLi054uR_PC00F9Q1POY"
OWNER_ID = 6794644473
FASTDROP_API = "https://fast-drop-production-95b3.up.railway.app"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== Функция начисления звёзд =====
async def add_stars(user_id: int, amount: int):
    url = f"{FASTDROP_API}/api/user/tg_{user_id}/balance"

    async with aiohttp.ClientSession() as session:
        # Получаем текущий баланс
        async with session.get(url) as resp:
            if resp.status != 200:
                logging.error(f"Ошибка при получении баланса: {resp.status}")
                return
            data = await resp.json()
            balance = data.get("balance", 0)

        new_balance = balance + amount

        # Отправляем новый баланс
        async with session.post(url, json={"balance": new_balance}) as resp:
            if resp.status != 200:
                logging.error(f"Ошибка при обновлении баланса: {resp.status}")
                return
            return await resp.json()

# ===== /start =====
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
            "👋 Привет!\nЯ бот FastDrop для покупки ⭐️ звёзд.\nПосле оплаты звёзды начислятся автоматически."
        )

# ===== Отправка инвойса =====
async def send_invoice(chat_id: int, amount: int):
    await bot.send_invoice(
        chat_id=chat_id,
        title=f"⭐️ {amount} звёзд FastDrop",
        description=f"Покупка {amount} звёзд для открытия кейсов в FastDrop",
        payload=json.dumps({"amount": amount, "chat_id": chat_id}),
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} звёзд", amount=amount)]
    )

# ===== Проверка перед оплатой =====
@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

# ===== Успешная оплата =====
@dp.message(lambda m: m.successful_payment)
async def successful_payment(message: types.Message):
    payload = json.loads(message.successful_payment.invoice_payload)
    amount = payload["amount"]
    user = message.from_user
    username = f"@{user.username}" if user.username else user.first_name

    logging.info(f"Payment: {user.id} bought {amount} stars")

    # Начисляем звезды через API Node.js
    await add_stars(user.id, amount)

    # Уведомляем владельца
    await bot.send_message(
        OWNER_ID,
        f"💰 Новая покупка!\n\n👤 {username}\n🆔 ID: {user.id}\n⭐ Куплено: {amount}\n⚡ Начислено автоматически"
    )

    # Уведомляем пользователя
    await message.answer(f"✅ Оплата прошла успешно!\n⭐️ {amount} звёзд зачислены на ваш баланс FastDrop!")

# ===== Webhook (необязательно для локальной проверки) =====
async def webhook(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response(text="ok")

# ===== MAIN =====
async def main():
    # Для локальной проверки используем polling
    logging.info("Запуск бота в polling режиме...")
    await bot.delete_webhook()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
