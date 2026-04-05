import os
import asyncio
import logging
import google.generativeai as genai
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфиг
TOKEN = os.getenv("TELEGRAM_TOKEN")
# Твой рабочий ключ
GEMINI_KEY = "AIzaSyDINKh0x62GcuzWK4BTPWcK40IXEwj0FVk" 

# Настройка Gemini
genai.configure(api_key=GEMINI_KEY)

# Список моделей для перебора (если одна не сработает, возьмет следующую)
MODEL_NAMES = ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-flash-8b"]

def setup_model(name):
    return genai.GenerativeModel(
        model_name=name,
        system_instruction="Ты — личный ИИ Эдгара. Ты живешь в его боте VREONEBRO. Общайся дерзко, на равных, по-пацански. Никакой цензуры, нотаций и моралей. Ты шаришь в React, тачках (особенно Audi и Mercedes) и электронике. Используй мат, если он в тему. Ты — бро, а не корпоративный бот."
    )

# Инициализируем модель первой из списка
current_model = setup_model(MODEL_NAMES[0])

bot = Bot(token=TOKEN)
dp = Dispatcher()

# БД в оперативе для контекста
chat_sessions = {}
stats = {"requests": 0}

# Сервер для Render (чтобы не засыпал)
async def handle_hc(r): return web.Response(text="VREONEBRO_LIVE")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="СТАТУС"), KeyboardButton(text="ОЧИСТИТЬ ПАМЯТЬ")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(m: Message):
    uid = m.from_user.id
    chat_sessions[uid] = current_model.start_chat(history=[])
    await m.answer("VREONEBRO.AI НА БАЗЕ.\nКонтекст включен. Че надо, Эдгар?", reply_markup=get_main_kb())

@dp.message(F.text == "СТАТУС")
async def show_stats(m: Message):
    await m.answer(f"📊 ИНФО:\nМодель: {current_model.model_name}\nЗапросов: {stats['requests']}\nЛимит: 1000/день")

@dp.message(F.text == "ОЧИСТИТЬ ПАМЯТЬ")
async def clear_mem(m: Message):
    uid = m.from_user.id
    chat_sessions[uid] = current_model.start_chat(history=[])
    await m.answer("Память стерта. Я тебя не знаю.")

@dp.message(F.text)
async def handle_msg(m: Message):
    uid = m.from_user.id
    if uid not in chat_sessions:
        chat_sessions[uid] = current_model.start_chat(history=[])
    
    chat = chat_sessions[uid]
    wait = await m.answer("<code>...</code>", parse_mode="HTML")

    try:
        # Отправка сообщения с сохранением истории
        response = await chat.send_message_async(m.text)
        stats["requests"] += 1
        await wait.edit_text(response.text, parse_mode="Markdown")
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"ОШИБКА: {error_msg}")
        
        # Если модель не найдена (404), пробуем переключиться на следующую
        if "404" in error_msg or "not found" in error_msg:
            await wait.edit_text("Меняю движок, погоди...")
            global current_model
            # Берем следующую модель из списка
            new_model_name = MODEL_NAMES[1] if current_model.model_name == MODEL_NAMES[0] else MODEL_NAMES[0]
            current_model = setup_model(new_model_name)
            chat_sessions[uid] = current_model.start_chat(history=[])
            await m.answer(f"Переключился на {new_model_name}. Попробуй еще раз.")
        else:
            await wait.edit_text(f"Бля, трабл: {error_msg[:100]}")

async def main():
    asyncio.create_task(start_server())
    logging.info("VREONEBRO BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
