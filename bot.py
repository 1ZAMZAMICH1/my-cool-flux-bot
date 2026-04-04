import os
import asyncio
import aiohttp
import random
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# Прямые ссылки на API Hugging Face (самый стабильный метод из твоего списка)
IMAGE_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
CHAT_URL = "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-72B-Instruct"

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_data = {}

# Сервер для Render (фикс портов)
async def handle_health_check(r): return web.Response(text="OK")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

def get_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🖼 Картинки"), KeyboardButton(text="💬 Чат")]], resize_keyboard=True)

async def call_api(url, payload, is_chat=True):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    # Чистим ответ от системного мусора
                    txt = data[0]['generated_text'] if isinstance(data, list) else data['generated_text']
                    return txt.split("assistant\n")[-1].strip()
                return f"Error: {resp.status}"
        except Exception as e: return f"Exception: {e}"

@dp.message(Command("start"))
async def start(m: Message):
    user_data[m.from_user.id] = "chat"
    await m.answer("🦾 **Neyro23 в здании.** Выбирай режим:", reply_markup=get_kb(), parse_mode="Markdown")

@dp.message(F.text == "🖼 Картинки")
async def m_img(m: Message):
    user_data[m.from_user.id] = "image"
    await m.answer("Отправь промпт на английском.")

@dp.message(F.text == "💬 Чат")
async def m_chat(m: Message):
    user_data[m.from_user.id] = "chat"
    await m.answer("Пиши любой вопрос.")

@dp.message(F.text)
async def handle(m: Message):
    mode = user_data.get(m.from_user.id, "chat")
    status = await m.answer("⌛️...")
    
    if mode == "image":
        res = await call_api(IMAGE_URL, {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="i.jpg"))
            await status.delete()
        else: await status.edit_text(f"Ошибка: {res}")
    else:
        # Промпт для Qwen 2.5 (одна из мощнейших бесплатных моделей)
        payload = {"inputs": f"<|system|>\nОтвечай четко на русском.\n<|user|>\n{m.text}\n<|assistant|>\n", "parameters": {"max_new_tokens": 700}}
        res = await call_api(CHAT_URL, payload)
        await status.edit_text(res)

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
