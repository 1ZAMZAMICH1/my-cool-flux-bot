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

client = genai.Client(api_key=GEMINI_KEY)
MODEL_NAME = "gemini-2.0-flash"

SYSTEM_PROMPT = (
    "Твое имя V-OneR. Общайся кратко и по делу. "
    "Никакой воды. Будь прямым, иногда резким. "
    "Если хамят — отвечай агрессивно и с матами. "
    "Ты — личность. Создатель — Эдгар."
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

# Хэндлер для Render (Health Check)
async def handle_hc(r): 
    return web.Response(text="V-OneR_LIVE", status=200)

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
        # Сборка контента
        contents = []
        for h in history:
            role = "model" if h['role'] == "model" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=h['content'])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=m.text)]))

        # Запрос
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: client.models.generate_content(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            contents=contents
        ))
        
        answer = response.text
        history.append({"role": "user", "content": m.text})
        history.append({"role": "model", "content": answer})
        save_history(uid, history)
        await wait.edit_text(answer)

    except Exception as e:
        logging.error(f"Error: {e}")
        await wait.edit_text(f"Трабл: {str(e)[:150]}")

async def main():
    # 1. Сначала запускаем веб-сервер, чтобы Render успокоился
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"SERVER STARTED ON PORT {port}")

    # 2. Теперь запускаем бота
    logging.info("V-OneR STARTING POLLING")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
