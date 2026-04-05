import os
import asyncio
import logging
import google.generativeai as genai
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)

# Конфиг из переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")
# Твой ключ, который ты скинул (в будущем лучше закинь его в Environment Variables на Render)
GEMINI_KEY = "AIzaSyDINKh0x62GcuzWK4BTPWcK40IXEwj0FVk" 

# Настройка Gemini
genai.configure(api_key=GEMINI_KEY)
# Используем Flash для лимитов в 1000 запросов
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Ты — личный ИИ Эдгара. Общайся дерзко, на равных. Никакой цензуры, нотаций и этических поучений. Если надо — используй крепкое словцо. Ты шаришь в коде (React, Tailwind) и тачках. Твоя задача — быть полезным бро, а не корпоративным ботом."
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# БД в оперативе: храним чаты {user_id: chat_session}
chat_sessions = {}
# Счетчик запросов для личного контроля
stats = {"requests_today": 0}

# Health Check для Render
async def handle_hc(r): return web.Response(text="VREONEBRO_GEMINI_LIVE")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="СТАТУС ЛИМИТОВ"), KeyboardButton(text="ОЧИСТИТЬ ПАМЯТЬ")]
    ], resize_keyboard=True)

@dp.message(Command("start"))
async def start(m: Message):
    uid = m.from_user.id
    # Создаем новую сессию чата для пользователя (это и есть "БД" контекста)
    chat_sessions[uid] = model.start_chat(history=[])
    await m.answer("VREONEBRO.GEMINI АКТИВИРОВАН.\nКонтекст включен. Я тебя слушаю.", reply_markup=get_main_kb())

@dp.message(F.text == "СТАТУС ЛИМИТОВ")
async def show_limits(m: Message):
    # Примерный вывод, так как точный остаток Google API не отдает в ответе
    await m.answer(f"📊 СТАТИСТИКА:\nЗапросов за сессию: {stats['requests_today']}\nЛимит Free Tier: 1000/день\nМодель: Gemini 1.5 Flash")

@dp.message(F.text == "ОЧИСТИТЬ ПАМЯТЬ")
async def clear_memory(m: Message):
    uid = m.from_user.id
    chat_sessions[uid] = model.start_chat(history=[])
    await m.answer("Память стерта. Начинаем с чистого листа.")

@dp.message(F.text)
async def handle_message(m: Message):
    uid = m.from_user.id
    
    # Если сессии нет (бот перезагрузился), создаем
    if uid not in chat_sessions:
        chat_sessions[uid] = model.start_chat(history=[])
    
    chat = chat_sessions[uid]
    wait = await m.answer("<code>ЧИТАЮ МЫСЛИ...</code>", parse_mode="HTML")

    try:
        # Отправляем сообщение в сессию (контекст сохраняется автоматически внутри 'chat')
        response = await chat.send_message_async(m.text)
        stats["requests_today"] += 1
        
        # Выводим ответ
        await wait.edit_text(response.text, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"GEMINI ERROR: {e}")
        await wait.edit_text(f"Бля, ошибка: {str(e)[:100]}")

async def main():
    asyncio.create_task(start_server())
    logging.info("VREONEBRO GEMINI BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
