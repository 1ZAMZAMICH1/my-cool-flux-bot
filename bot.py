import os, asyncio, logging
from google import genai
from google.genai import types
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web
from tinydb import TinyDB, Query

# Логирование только важных событий
logging.basicConfig(level=logging.INFO)

# Ключи из Environment Render
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# Инициализация БД (Файл создастся автоматически при первом сообщении)
db = TinyDB('db.json')
UQuery = Query()

client = genai.Client(api_key=GEMINI_KEY)
MODEL_NAME = "gemini-2.0-flash"

# ИСПРАВЛЕННЫЙ ХАРАКТЕР: КРАТКОСТЬ И ПРЯМОТА
SYSTEM_PROMPT = (
    "Твое имя V-OneR. Ты общаешься как реальный человек, а не бот. "
    "Твой стиль: максимально кратко и по делу. Не лей воду, не здоровайся каждый раз, "
    "не расписывай очевидные вещи, если тебя об этом не просят. "
    "Будь прямым, иногда резким. Если собеседник тупит или ведет себя неуважительно — "
    "отвечай жестко, с матами, ставь на место. В остальном — спокойный, уверенный тон. "
    "Никогда не упоминай, что ты ИИ или нейросеть. Ты — V-OneR. Создатель — Эдгар."
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

def get_history(uid):
    try:
        res = db.search(UQuery.id == uid)
        return res[0]['history'] if res else []
    except: return []

def save_history(uid, history):
    # Храним последние 10 реплик для контекста
    db.upsert({'id': uid, 'history': history[-10:]}, UQuery.id == uid)

async def handle_hc(r): return web.Response(text="V-OneR_LIVE")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()

@dp.message(Command("start"))
async def start(m: Message):
    save_history(m.from_user.id, [])
    await m.answer("На связи. Что хотел?")

@dp.message(F.text)
async def handle_msg(m: Message):
    uid = m.from_user.id
    history = get_history(uid)
    
    # Визуальный индикатор работы
    wait = await m.answer("...")

    try:
        # Формируем историю для Gemini
        contents = []
        for h in history:
            contents.append(types.Content(role=h['role'], parts=[types.Part(text=h['content'])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=m.text)]))

        # Запрос к нейронке
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: client.models.generate_content(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            contents=contents
        ))
        
        answer = response.text
        
        # Обновляем историю в БД
        history.append({"role": "user", "content": m.text})
        history.append({"role": "model", "content": answer})
        save_history(uid, history)
        
        # Выводим ответ
        await wait.edit_text(answer)
        
    except Exception as e:
        error_log = str(e)
        logging.error(f"Ошибка: {error_log}")
        if "400" in error_log or "403" in error_log:
            await wait.edit_text("Проблема с ключом Gemini. Проверь API_KEY.")
        else:
            await wait.edit_text("Затупил я что-то. Повтори.")

async def main():
    asyncio.create_task(start_server())
    logging.info("V-OneR READY")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
