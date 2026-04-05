import os, asyncio, logging
from google import genai
from google.genai import types
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiohttp import web
from tinydb import TinyDB, Query

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

db = TinyDB('db.json')
UQuery = Query()

# Инициализация клиента
client = genai.Client(api_key=GEMINI_KEY)
MODEL_NAME = "gemini-2.0-flash"

SYSTEM_PROMPT = (
    "Твое имя V-OneR. Ты общаешься кратко и по делу. "
    "Никакой воды и лишних приветствий. Будь прямым, иногда резким. "
    "Если хамят — отвечай агрессивно и с матами. Ты — личность, а не ИИ. "
    "Создатель — Эдгар."
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_history(uid):
    try:
        res = db.search(UQuery.id == uid)
        return res[0]['history'] if res else []
    except: return []

def save_history(uid, history):
    db.upsert({'id': uid, 'history': history[-10:]}, UQuery.id == uid)

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
    await m.answer("На связи. Че хотел?")

@dp.message(F.text)
async def handle_msg(m: Message):
    uid = m.from_user.id
    history = get_history(uid)
    wait = await m.answer("...")

    try:
        # Подготовка контента для Google SDK
        contents = []
        for h in history:
            # Важно: роль должна быть строго 'user' или 'model'
            role_name = "model" if h['role'] == "model" else "user"
            contents.append(types.Content(role=role_name, parts=[types.Part(text=h['content'])]))
        
        # Добавляем текущее сообщение
        contents.append(types.Content(role="user", parts=[types.Part(text=m.text)]))

        # Запрос к нейронке (используем синхронный вызов через executor)
        loop = asyncio.get_running_loop()
        def call_gemini():
            return client.models.generate_content(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                contents=contents
            )

        response = await loop.run_in_executor(None, call_gemini)
        answer = response.text

        # Сохраняем в историю
        history.append({"role": "user", "content": m.text})
        history.append({"role": "model", "content": answer})
        save_history(uid, history)

        await wait.edit_text(answer)

    except Exception as e:
        # ВЫВОДИМ РЕАЛЬНУЮ ОШИБКУ, ЧТОБЫ ПОНЯТЬ В ЧЕМ ДЕЛО
        error_text = str(e)
        logging.error(f"ПОЛНАЯ ОШИБКА: {error_text}")
        await wait.edit_text(f"Трабл: {error_text[:200]}")

async def main():
    asyncio.create_task(start_server())
    logging.info("V-OneR READY")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
