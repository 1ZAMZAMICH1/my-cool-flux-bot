import os
import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

# КЛЮЧИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# URL-адреса API
FLUX_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GOOGLE_API_KEY}"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Простейшее хранилище состояний (в памяти)
user_modes = {} # {user_id: "image" или "chat"}

def get_keyboard():
    buttons = [
        [KeyboardButton(text="🖼 Генерация картинок"), KeyboardButton(text="🤖 Чат с Gemini")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def call_gemini(text):
    payload = {"contents": [{"parts": [{"text": text}]}]}
    async with aiohttp.ClientSession() as session:
        async with session.post(GEMINI_URL, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            return "❌ Ошибка Gemini. Проверь API ключ."

async def call_flux(prompt):
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.post(FLUX_URL, headers=headers, json={"inputs": prompt}, timeout=60) as resp:
            if resp.status == 200: return await resp.read()
            if resp.status == 503: return "busy"
            return None

@dp.message(Command("start"))
async def start(message: Message):
    user_modes[message.from_user.id] = "chat"
    await message.answer("Здарова! Я обновился. Выбери режим на кнопках ниже:", reply_markup=get_keyboard())

@dp.message(F.text == "🖼 Генерация картинок")
async def set_mode_img(message: Message):
    user_modes[message.from_user.id] = "image"
    await message.answer("Режим переключен на ГЕНЕРАЦИЮ. Пиши промпт!")

@dp.message(F.text == "🤖 Чат с Gemini")
async def set_mode_chat(message: Message):
    user_modes[message.from_user.id] = "chat"
    await message.answer("Режим переключен на ЧАТ. Спрашивай что угодно!")

@dp.message(F.text)
async def handle_all(message: Message):
    mode = user_modes.get(message.from_user.id, "chat")
    
    if mode == "image":
        status = await message.answer("🎨 Рисую...")
        img = await call_flux(message.text)
        if img == "busy":
            await status.edit_text("⏳ Сервер занят, попробуй через минуту.")
        elif img:
            await message.answer_photo(BufferedInputFile(img, filename="pic.jpg"))
            await status.delete()
        else:
            await status.edit_text("❌ Ошибка генерации.")
            
    else: # Режим ЧАТА
        status = await message.answer("🤔 Думаю...")
        response = await call_gemini(message.text)
        await status.edit_text(response)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
