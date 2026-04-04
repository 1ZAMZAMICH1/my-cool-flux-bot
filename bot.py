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

# КЛЮЧИ
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ИСПРАВЛЕННЫЕ ССЫЛКИ 2026
IMAGE_MODEL_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
# Используем Qwen 2.5 72B — она мощнее и лучше понимает русский через этот API
CHAT_MODEL_URL = "https://router.huggingface.co/hf-inference/models/Qwen/Qwen2.5-72B-Instruct"

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_data = {}

# ФИКС ПОРТОВ ДЛЯ RENDER
async def handle_health_check(request):
    return web.Response(text="Бот активен")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎨 Генерация изображений"), KeyboardButton(text="💬 Интеллектуальный чат")]],
        resize_keyboard=True
    )

async def call_hf_api(url, payload):
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=90) as resp:
                if resp.status == 200:
                    if "black-forest-labs" in url:
                        return await resp.read() # Картинка
                    data = await resp.json()
                    # Парсим ответ от чат-модели
                    if isinstance(data, list):
                        return data[0].get('generated_text', '').split('assistant\n')[-1].strip()
                    return data.get('generated_text', '').split('assistant\n')[-1].strip()
                
                err_info = await resp.text()
                logging.error(f"HF Error {resp.status}: {err_info}")
                return f"error_{resp.status}"
        except Exception as e:
            logging.error(f"API Exception: {e}")
            return None

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_data[message.from_user.id] = "chat"
    await message.answer("🚀 **Система Neyro23 готова!**\n\nВыбери режим работы ниже.", 
                         parse_mode="Markdown", reply_markup=main_keyboard())

@dp.message(F.text == "🎨 Генерация изображений")
async def mode_image(message: Message):
    user_data[message.from_user.id] = "image"
    await message.answer("🖼 Режим: **Генерация**. Жду описание на английском.", parse_mode="Markdown")

@dp.message(F.text == "💬 Интеллектуальный чат")
async def mode_chat(message: Message):
    user_data[message.from_user.id] = "chat"
    await message.answer("💬 Режим: **Чат**. Спрашивай о чем угодно на русском!", parse_mode="Markdown")

@dp.message(F.text)
async def process_request(message: Message):
    mode = user_data.get(message.from_user.id, "chat")
    
    if mode == "image":
        status = await message.answer("⏳ Рисую...")
        res = await call_hf_api(IMAGE_MODEL_URL, {"inputs": message.text, "parameters": {"seed": random.randint(0, 999999)}})
        if isinstance(res, bytes):
            await message.answer_photo(BufferedInputFile(res, filename="gen.jpg"), caption="Готово!")
            await status.delete()
        else:
            await status.edit_text(f"❌ Ошибка генерации: {res}")
            
    else: # Режим чата
        status = await message.answer("💭 Думаю...")
        prompt = f"<|system|>\nТы — полезный ИИ-помощник. Отвечай на русском языке.\n<|user|>\n{message.text}\n<|assistant|>\n"
        res = await call_hf_api(CHAT_MODEL_URL, {"inputs": prompt, "parameters": {"max_new_tokens": 800}})
        if res and not res.startswith("error_"):
            await status.edit_text(res)
        else:
            await status.edit_text(f"❌ Ошибка модели: {res}")

async def main():
    asyncio.create_task(start_web_server())
    logging.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
