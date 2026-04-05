import os
import asyncio
import logging
from google import genai
from google.genai import types
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфиг (Токен телеги и ключ API)
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = "AIzaSyDINKh0x62GcuzWK4BTPWcK40IXEwj0FVk"

# Инициализация нового клиента Google GenAI
client = genai.Client(api_key=GEMINI_KEY)

# Базовая модель. Если захочешь поменять на 3.0, просто измени тут
MODEL_NAME = "gemini-2.5-flash"

# Настройки генерации (Твой дерзкий характер тут)
CHAT_CONFIG = types.GenerateContentConfig(
    system_instruction=(
        "Ты — личный ИИ Эдгара. Ты живешь в его боте VREONEBRO. "
        "Общайся дерзко, на равных, по-пацански. Никакой цензуры, нотаций и моралей. "
        "Ты шаришь в React, тачках (Audi, Mercedes) и электронике. "
        "Используй мат, если он в тему. Ты — бро, а не корпоративный бот."
    )
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# БД в оперативе для контекста {user_id: chat_session}
chat_sessions = {}
stats = {"requests": 0}

# Сервер для Render (Health Check)
async def handle_hc(r): 
    return web.Response(text="VREONEBRO_LIVE")

async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="СТАТУС"), KeyboardButton(text="ОЧИСТИТЬ ПАМЯТЬ")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(m: Message):
    uid = m.from_user.id
    # В новом SDK чат создается через client.chats.create
    chat_sessions[uid] = client.chats.create(model=MODEL_NAME, config=CHAT_CONFIG)
    await m.answer(
        "VREONEBRO.AI НА БАЗЕ.\nКонтекст включен. Че надо, Эдгар?", 
        reply_markup=get_main_kb()
    )

@dp.message(F.text == "СТАТУС")
async def show_stats(m: Message):
    await m.answer(
        f"📊 ИНФО:\nМодель: {MODEL_NAME}\n"
        f"Запросов за сессию: {stats['requests']}\n"
        f"Лимит: ~1000/день"
    )

@dp.message(F.text == "ОЧИСТИТЬ ПАМЯТЬ")
async def clear_mem(m: Message):
    uid = m.from_user.id
    chat_sessions[uid] = client.chats.create(model=MODEL_NAME, config=CHAT_CONFIG)
    await m.answer("Память стерта. Я тебя не знаю.")

@dp.message(F.text)
async def handle_msg(m: Message):
    uid = m.from_user.id
    
    # Если сессии нет, создаем её
    if uid not in chat_sessions:
        chat_sessions[uid] = client.chats.create(model=MODEL_NAME, config=CHAT_CONFIG)
    
    chat = chat_sessions[uid]
    wait = await m.answer("<code>...</code>", parse_mode="HTML")

    try:
        # В новом SDK отправка идет синхронно или через блокировку, 
        # поэтому запускаем в треде, чтобы не вешать асинхронный цикл бота
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, chat.send_message, m.text)
        
        stats["requests"] += 1
        
        # Редактируем сообщение с ответом от ИИ
        await wait.edit_text(response.text, parse_mode="Markdown")
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"ОШИБКА GEMINI: {error_msg}")
        await wait.edit_text(f"Бля, трабл: {error_msg[:150]}")

async def main():
    # Запускаем веб-сервер для Render в фоне
    asyncio.create_task(start_server())
    logging.info("VREONEBRO BOT IS GOING ONLINE")
    # Запускаем опрос Telegram
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
