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

# Конфиг (Токен телеги и ключ API)
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = "AIzaSyDINKh0x62GcuzWK4BTPWcK40IXEwj0FVk" 

# Настройка Gemini
genai.configure(api_key=GEMINI_KEY)

# Список моделей для перебора в случае 404 ошибки
MODEL_NAMES = ["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash-8b"]

def setup_model(name):
    """Функция для инициализации модели с системным промптом"""
    return genai.GenerativeModel(
        model_name=name,
        system_instruction=(
            "Ты — личный ИИ Эдгара. Ты живешь в его боте VREONEBRO. "
            "Общайся дерзко, на равных, по-пацански. Никакой цензуры, нотаций и моралей. "
            "Ты шаришь в React, тачках (Audi, Mercedes) и электронике. "
            "Используй мат, если он в тему. Ты — бро, а не корпоративный бот."
        )
    )

# Инициализируем текущую модель
current_model = setup_model(MODEL_NAMES[0])

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
    # Создаем новую сессию чата (Контекст)
    chat_sessions[uid] = current_model.start_chat(history=[])
    await m.answer(
        "VREONEBRO.AI НА БАЗЕ.\nКонтекст включен. Че надо, Эдгар?", 
        reply_markup=get_main_kb()
    )

@dp.message(F.text == "СТАТУС")
async def show_stats(m: Message):
    await m.answer(
        f"📊 ИНФО:\nМодель: {current_model.model_name}\n"
        f"Запросов за сессию: {stats['requests']}\n"
        f"Лимит: ~1000/день"
    )

@dp.message(F.text == "ОЧИСТИТЬ ПАМЯТЬ")
async def clear_mem(m: Message):
    uid = m.from_user.id
    chat_sessions[uid] = current_model.start_chat(history=[])
    await m.answer("Память стерта. Я тебя не знаю.")

@dp.message(F.text)
async def handle_msg(m: Message):
    global current_model # Теперь объявление в самом начале функции, ошибки не будет
    uid = m.from_user.id
    
    # Если сессии нет, создаем её
    if uid not in chat_sessions:
        chat_sessions[uid] = current_model.start_chat(history=[])
    
    chat = chat_sessions[uid]
    wait = await m.answer("<code>...</code>", parse_mode="HTML")

    try:
        # Отправка сообщения в Gemini через SDK (автоматически хранит историю)
        response = await chat.send_message_async(m.text)
        stats["requests"] += 1
        
        # Редактируем сообщение с ответом от ИИ
        await wait.edit_text(response.text, parse_mode="Markdown")
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"ОШИБКА GEMINI: {error_msg}")
        
        # Если модель не найдена (404), пробуем переключиться
        if "404" in error_msg or "not found" in error_msg:
            await wait.edit_text("Меняю движок, погоди...")
            
            # Переключаемся на следующую модель из списка
            idx = MODEL_NAMES.index(current_model.model_name)
            new_idx = (idx + 1) % len(MODEL_NAMES)
            current_model = setup_model(MODEL_NAMES[new_idx])
            
            # Пересоздаем сессию для новой модели
            chat_sessions[uid] = current_model.start_chat(history=[])
            await m.answer(f"Переключился на {current_model.model_name}. Попробуй еще раз.")
        else:
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
