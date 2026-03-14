import os
import json
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
import asyncio

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8657069014:AAECyVfbXP3ta9dWLi054uR_PC00F9Q1POY')
OWNER_ID = int(os.environ.get('OWNER_ID', '6794644473'))
API_BASE = os.environ.get('API_BASE', 'https://fast-drop-production-95b3.up.railway.app')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== API ФУНКЦИИ =====
async def api_get(path):
    """GET запрос к серверу"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{API_BASE}{path}') as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f'API GET error: {e}')
    return None

async def api_post(path, data):
    """POST запрос к серверу"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_BASE}{path}', json=data) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f'API POST error: {e}')
    return None

async def get_user_balance(user_id):
    """Получить баланс пользователя"""
    data = await api_get(f'/api/user/tg_{user_id}/balance')
    return data.get('balance', 0) if data else 0

async def set_user_balance(user_id, balance):
    """Установить баланс пользователя"""
    return await api_post(f'/api/user/tg_{user_id}/balance', {'balance': balance})

# ===== ОБРАБОТЧИКИ =====
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    args = message.text.split()
    
    # Deep link для покупки: /start buy_500
    if len(args) > 1 and args[1].startswith('buy_'):
        try:
            amount = int(args[1].replace('buy_', ''))
            if amount < 1:
                await message.answer('❌ Минимум 1 звезда!')
                return
            if amount > 10000:
                await message.answer('❌ Максимум 10000 звёзд за раз!')
                return
            await send_invoice(message.chat.id, message.from_user.id, amount)
        except ValueError:
            await message.answer('❌ Неверное количество звёзд!')
        return
    
    # Обычный старт
    balance = await get_user_balance(message.from_user.id)
    
    await message.answer(
        f'👋 Привет, {message.from_user.first_name}!\n\n'
        f'🎁 <b>FastDrop</b> — открывай кейсы и выигрывай призы!\n\n'
        f'💰 Ваш баланс: <b>{balance} ⭐️</b>\n\n'
        f'📦 Команды:\n'
        f'/buy <кол-во> — купить звёзды\n'
        f'/balance — проверить баланс\n'
        f'/help — помощь',
        parse_mode=ParseMode.HTML
    )

@dp.message(Command('help'))
async def cmd_help(message: types.Message):
    await message.answer(
        '📖 <b>Помощь FastDrop</b>\n\n'
        '⭐️ <b>Покупка звёзд:</b>\n'
        '• /buy 100 — купить 100 звёзд\n'
        '• /buy 500 — купить 500 звёзд\n\n'
        '💰 <b>Баланс:</b>\n'
        '• /balance — текущий баланс\n\n'
        '🎁 <b>Кейсы:</b>\n'
        'Открывайте кейсы в приложении FastDrop!\n\n'
        '❓ <b>Поддержка:</b>\n'
        '@Marixbuvshuypsevd\n'
        '@blackrfly',
        parse_mode=ParseMode.HTML
    )

@dp.message(Command('balance'))
async def cmd_balance(message: types.Message):
    balance = await get_user_balance(message.from_user.id)
    await message.answer(
        f'💰 <b>Ваш баланс</b>\n\n'
        f'⭐️ Звёзд: <b>{balance}</b>',
        parse_mode=ParseMode.HTML
    )

@dp.message(Command('buy'))
async def cmd_buy(message: types.Message):
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            '💫 <b>Покупка звёзд</b>\n\n'
            'Укажите количество:\n'
            '/buy 100\n'
            '/buy 500\n'
            '/buy 1000',
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        amount = int(args[1])
        if amount < 1:
            await message.answer('❌ Минимум 1 звезда!')
            return
        if amount > 10000:
            await message.answer('❌ Максимум 10000 звёзд за раз!')
            return
        await send_invoice(message.chat.id, message.from_user.id, amount)
    except ValueError:
        await message.answer('❌ Укажите число! Пример: /buy 500')

async def send_invoice(chat_id, user_id, amount):
    """Отправка счёта для оплаты"""
    try:
        await bot.send_invoice(
            chat_id=chat_id,
            title=f'⭐️ {amount} звёзд FastDrop',
            description=f'Покупка {amount} звёзд для открытия кейсов',
            payload=json.dumps({
                'type': 'stars',
                'amount': amount,
                'user_id': user_id
            }),
            currency='XTR',
            prices=[types.LabeledPrice(label=f'{amount} звёзд', amount=amount)]
        )
    except Exception as e:
        logger.error(f'Invoice error: {e}')
        await bot.send_message(chat_id, '❌ Ошибка создания счёта. Попробуйте позже.')

@dp.pre_checkout_query()
async def on_pre_checkout(query: types.PreCheckoutQuery):
    """Подтверждение платежа"""
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(lambda m: m.successful_payment is not None)
async def on_successful_payment(message: types.Message):
    """Обработка успешной оплаты"""
    payment = message.successful_payment
    
    try:
        payload = json.loads(payment.invoice_payload)
        amount = payload.get('amount', 0)
        user_id = message.from_user.id
        
        # Получаем текущий баланс
        current_balance = await get_user_balance(user_id)
        new_balance = current_balance + amount
        
        # Обновляем баланс на сервере
        await set_user_balance(user_id, new_balance)
        
        # Формируем username
        user = message.from_user
        username = f'@{user.username}' if user.username else user.first_name
        
        # Уведомляем владельца
        await bot.send_message(
            OWNER_ID,
            f'💰 <b>Новая покупка!</b>\n\n'
            f'👤 Пользователь: {username}\n'
            f'🆔 ID: <code>{user_id}</code>\n'
            f'⭐️ Куплено: <b>{amount}</b> звёзд\n'
            f'💵 Telegram Stars: {payment.total_amount} XTR\n'
            f'💰 Новый баланс: <b>{new_balance}</b>\n'
            f'🕐 {message.date.strftime("%d.%m.%Y %H:%M:%S")}',
            parse_mode=ParseMode.HTML
        )
        
        # Уведомляем пользователя
        await message.answer(
            f'✅ <b>Оплата успешна!</b>\n\n'
            f'⭐️ Начислено: <b>+{amount}</b> звёзд\n'
            f'💰 Ваш баланс: <b>{new_balance}</b> звёзд\n\n'
            f'🎁 Откройте FastDrop и играйте!',
            parse_mode=ParseMode.HTML
        )
        
        logger.info(f'Payment success: user={user_id}, amount={amount}, new_balance={new_balance}')
        
    except Exception as e:
        logger.error(f'Payment processing error: {e}')
        await message.answer('⚠️ Оплата получена! Звёзды будут начислены в течение минуты.')
        
        # Уведомляем владельца об ошибке
        await bot.send_message(
            OWNER_ID,
            f'⚠️ <b>Ошибка обработки платежа!</b>\n\n'
            f'👤 ID: {message.from_user.id}\n'
            f'💵 Сумма: {payment.total_amount} XTR\n'
            f'❌ Ошибка: {str(e)}',
            parse_mode=ParseMode.HTML
        )

# ===== АДМИН КОМАНДЫ =====
@dp.message(Command('admin'))
async def cmd_admin(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        '👑 <b>Админ-панель</b>\n\n'
        '/addstars <id> <кол-во> — начислить звёзды\n'
        '/setstars <id> <кол-во> — установить баланс\n'
        '/checkuser <id> — проверить пользователя',
        parse_mode=ParseMode.HTML
    )

@dp.message(Command('addstars'))
async def cmd_addstars(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer('Использование: /addstars <user_id> <amount>')
        return
    
    try:
        target_id = int(args[1])
        amount = int(args[2])
        
        current = await get_user_balance(target_id)
        new_balance = current + amount
        await set_user_balance(target_id, new_balance)
        
        await message.answer(
            f'✅ Начислено!\n\n'
            f'👤 ID: {target_id}\n'
            f'➕ Добавлено: {amount} ⭐️\n'
            f'💰 Новый баланс: {new_balance} ⭐️'
        )
        
        # Уведомляем пользователя
        try:
            await bot.send_message(
                target_id,
                f'🎁 <b>Вам начислены звёзды!</b>\n\n'
                f'⭐️ +{amount} звёзд\n'
                f'💰 Баланс: {new_balance} звёзд',
                parse_mode=ParseMode.HTML
            )
        except:
            pass
            
    except ValueError:
        await message.answer('❌ Неверный формат!')

@dp.message(Command('setstars'))
async def cmd_setstars(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer('Использование: /setstars <user_id> <amount>')
        return
    
    try:
        target_id = int(args[1])
        amount = int(args[2])
        
        await set_user_balance(target_id, amount)
        
        await message.answer(
            f'✅ Баланс установлен!\n\n'
            f'👤 ID: {target_id}\n'
            f'💰 Баланс: {amount} ⭐️'
        )
    except ValueError:
        await message.answer('❌ Неверный формат!')

@dp.message(Command('checkuser'))
async def cmd_checkuser(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer('Использование: /checkuser <user_id>')
        return
    
    try:
        target_id = int(args[1])
        balance = await get_user_balance(target_id)
        
        await message.answer(
            f'👤 <b>Пользователь</b>\n\n'
            f'🆔 ID: <code>{target_id}</code>\n'
            f'💰 Баланс: <b>{balance}</b> ⭐️',
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer('❌ Неверный ID!')

# ===== ЗАПУСК =====
async def main():
    logger.info('Starting FastDrop Bot...')
    
    # Удаляем webhook если был
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем polling
    logger.info('Bot started!')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
