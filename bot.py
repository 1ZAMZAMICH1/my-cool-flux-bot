import os
import asyncio
import aiohttp
import random
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command

# Настройка логов, чтобы видеть ошибки в консоли Render
logging.basicConfig(level=logging.INFO)

# Получаем ключи из переменных окружения (Environment Variables)
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
MODEL_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"

# Проверка ключей перед запуском
if not TOKEN or not HF_TOKEN:
    print("❌ ОШИБКА: Забыли прописать TELEGRAM_TOKEN или HF_TOKEN в настройках!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

async def get_image(prompt: str):
    """Функция запроса к нейронке Flux через Hugging Face"""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {"seed": random.randint(0, 1000000)}
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(MODEL_URL, headers=headers, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    return await resp.read()
                elif resp.status == 503:
                    return "busy"
                else:
                    error_text = await resp.text()
                    logging.error(f"HF Error: {resp.status} - {error_text}")
                    return None
        except Exception as e:
            logging.error(f"Request error: {e}")
            return None

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer("Приуэт! Я твой личный генератор картинок на базе Flux.1.\n\nПросто напиши мне, что нарисовать (лучше на английском)!")

@dp.message(F.text)
async def handle_text(message: Message):
    # Уведомляем юзера, что процесс пошел
    status_msg = await message.answer("🎨 Малюю... Это займет секунд 10-15.")
    
    image_data = await get_image(message.text)
    
    if image_data == "busy":
        await status_msg.edit_text("⏳ Сервера Hugging Face сейчас заняты (ошибка 503). Попробуй еще раз через минуту!")
    elif image_data:
        try:
            photo = BufferedInputFile(image_data, filename="result.jpg")
            await message.answer_photo(photo=photo, caption=f"Твой запрос: {message.text[:100]}")
            await status_msg.delete()
        except Exception as e:
            logging.error(f"Send photo error: {e}")
            await status_msg.edit_text("❌ Ошибка при отправке фото в Telegram.")
    else:
        await status_msg.edit_text("❌ Не удалось сгенерировать. Попробуй изменить промпт или подождать.")

async def main():
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
