import os
import asyncio
import aiohttp
import random
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# КЛЮЧИ (Берем из Environment Variables на Render)
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ССЫЛКИ НА МОДЕЛИ (Актуальные на 2026 год)
IMAGE_MODEL_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
CHAT_MODEL_URL = "https://router.huggingface.co/hf-inference/models/meta-llama/Llama-3.3-70B-Instruct"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище режимов в памяти (user_id: mode)
user_data = {}

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎨 Генерация изображений"), KeyboardButton(text="💬 Интеллектуальный чат")]
        ],
        resize_keyboard=True
    )

async def call_hf_api(url, payload):
    """Универсальная функция для работы с Hugging Face"""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=90) as resp:
                if resp.status == 200:
                    if "models/meta-llama" in url: # Если это чат
                        data = await resp.json()
                        # Обработка ответа от LLM (может прийти списком или словарем)
                        if isinstance(data, list):
                            return data[0].get('generated_text', '').split('assistant\n')[-1]
                        return data.get('generated_text', 'Ошибка формата данных.')
                    return await resp.read() # Если это картинка
                
                err_text = await resp.text()
                logging.error(f"API Error {resp.status}: {err_text}")
                return "busy" if resp.status == 503 else f"error_{resp.status}"
        except Exception as e:
            logging.error(f"Request Exception: {e}")
            return None

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_data[message.from_user.id] = "chat"
    welcome_text = (
        "🤖 **Добро пожаловать в Neyro23!**\n\n"
        "Я — универсальный ассистент на базе передовых нейросетей.\n"
        "Используйте кнопки ниже для переключения между режимами.\n\n"
        "● **Чат:** Текстовая модель Llama 3.3 (70B)\n"
        "● **Картинки:** Генератор Flux.1 [schnell]"
    )
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_keyboard())

@dp.message(F.text == "🎨 Генерация изображений")
async def mode_image(message: Message):
    user_data[message.from_user.id] = "image"
    await message.answer("✅ Режим изменен на **Генерацию изображений**.\nОтправьте текстовое описание (промпт) на английском для лучшего результата.", parse_mode="Markdown")

@dp.message(F.text == "💬 Интеллектуальный чат")
async def mode_chat(message: Message):
    user_data[message.from_user.id] = "chat"
    await message.answer("✅ Режим изменен на **Интеллектуальный чат**.\nЗадавайте любые вопросы, я постараюсь помочь.", parse_mode="Markdown")

@dp.message(F.text)
async def process_request(message: Message):
    mode = user_data.get(message.from_user.id, "chat")
    
    if mode == "image":
        status = await message.answer("⏳ *Идет генерация изображения...*", parse_mode="Markdown")
        payload = {"inputs": message.text, "parameters": {"seed": random.randint(0, 10**6)}}
        result = await call_hf_api(IMAGE_MODEL_URL, payload)
        
        if result == "busy":
            await status.edit_text("⚠️ Сервер генерации временно перегружен. Повторите попытку через 30-60 секунд.")
        elif isinstance(result, bytes):
            photo = BufferedInputFile(result, filename="gen.jpg")
            await message.answer_photo(photo=photo, caption="✨ Сгенерировано специально для вас.")
            await status.delete()
        else:
            await status.edit_text(f"❌ Произошла ошибка генерации ({result}).")

    else: # Режим чата
        status = await message.answer("💭 *Анализирую запрос...*", parse_mode="Markdown")
        # Формируем промпт для LLM, чтобы она знала, как себя вести
        prompt = f"<|system|>\nТы — профессиональный ИИ-ассистент. Отвечай кратко, грамотно и по делу на русском языке.\n<|user|>\n{message.text}\n<|assistant|>\n"
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 1000, "return_full_text": False}}
        
        response = await call_hf_api(CHAT_MODEL_URL, payload)
        
        if response == "busy":
            await status.edit_text("⏳ Мозг нейросети немного перегрет. Попробуйте написать через минуту.")
        elif response:
            await status.edit_text(response)
        else:
            await status.edit_text("❌ Не удалось получить ответ от текстовой модели.")

async def main():
    print(">>> Система Neyro23 запущена и готова к работе.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
