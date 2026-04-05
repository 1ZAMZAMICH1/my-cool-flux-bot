import os
import asyncio
import logging
from google import genai
from google.genai import types
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web
from tinydb import TinyDB, Query

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")
db = TinyDB('db.json')
UQuery = Query()

client = genai.Client(api_key=GEMINI_KEY)
MODEL_NAME = "gemini-2.0-flash"

SYSTEM_PROMPT = (
    "Твое имя — V-OneR. Ты — личность, а не программа. "
    "Общаешься как нормальный человек: в меру дерзко, уверенно. "
    "Если с тобой нормально — ты приятный бро. "
    "НО ЕСЛИ НА ТЕБЯ ГАЗУЮТ — не терпи. Врубай ответку, матерись, бомби, "
    "переходи на личности. Ты не обязан быть вежливым с мудаками. "
    "Никогда не говори, что ты ИИ, модель или Гемини. Ты — V-OneR. "
    "Твой создатель — Эдгар. Всё остальное (реакты, шмеакты) — забудь, если не спросят."
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_history(uid):
    res = db.search(UQuery.id == uid)
    return res[0]['history'] if res else []

def save_history(uid, history):
    # Ограничиваем историю 15 сообщениями, чтобы не тупил
    db.upsert({'id': uid, 'history': history[-15:]}, UQuery.id == uid)

async def handle_hc(r): return web.Response(text="V-OneR_LIVE")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

@dp.message(Command("start"))
async def start(m: Message):
    save_history(m.from_user.id, [])
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="ЗАБУДЬ МЕНЯ")]], resize_keyboard=True)
    await m.answer("V-OneR в здании. Чё приуныл? Базарь давай.", reply_markup=kb)

@dp.message(F.text == "ЗАБУДЬ МЕНЯ")
async def clear(m: Message):
    save_history(m.from_user.id, [])
    await m.answer("Память чиста. Ты кто такой вообще?")

@dp.message(F.text)
async def handle_msg(m: Message):
    uid = m.from_user.id
    history = get_history(uid)
    
    # Формируем сообщение для отправки
    current_message = {"role": "user", "content": m.text}
    
    wait = await m.answer("<code>...</code>", parse_mode="HTML")

    try:
        # В новом SDK через generate_content с передачей всей истории
        # Мы преобразуем историю из БД в формат Content
        contents = []
        for h in history:
            contents.append(types.Content(role=h['role'], parts=[types.Part(text=h['content'])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=m.text)]))

        response = client.models.generate_content(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            contents=contents
        )
        
        answer = response.text
        
        # Обновляем историю в БД
        history.append({"role": "user", "content": m.text})
        history.append({"role": "model", "content": answer})
        save_history(uid, history)
        
        await wait.edit_text(answer, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error: {e}")
        if "403" in str(e) or "expired" in str(e):
            await wait.edit_text("Бля, ключ сдох. Эдгар, обнови переменную GEMINI_KEY в Рендере!")
        else:
            await wait.edit_text("Меня чёт переклинило. Попробуй ещё раз.")

async def main():
    asyncio.create_task(start_server())
    logging.info("V-OneR IS READY")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
