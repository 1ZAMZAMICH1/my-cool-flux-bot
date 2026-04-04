import os
import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

# Настройка логирования для отладки в Render
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ТВОЙ ПРОВЕРЕННЫЙ НАБОР
MODELS = {
    "text": {
        "Gemma 2 (Google)": "google/gemma-2-9b-it",
        "Llama 3 (Meta)": "meta-llama/Meta-Llama-3-8B-Instruct",
        "Mistral 7B": "mistralai/Mistral-7B-Instruct-v0.3"
    },
    "image": {
        "SD 3.5 Large": "stabilityai/stable-diffusion-3.5-large",
        "FLUX.1 (Fast)": "black-forest-labs/FLUX.1-schnell"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_config = {}

# Сервер для хелсчека Render
async def handle_hc(r): return web.Response(text="VREONEBRO_LIVE")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info(f"Web server started on port {port}")

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="ВЫБОР МОДЕЛЕЙ"), KeyboardButton(text="ВЫБОР ХУДОЖНИКОВ")],
        [KeyboardButton(text="РЕЖИМ: ЧАТ"), KeyboardButton(text="РЕЖИМ: ФОТО")]
    ], resize_keyboard=True)

async def call_hf_api(model_id, payload, is_chat=True):
    # Прямой адрес через роутер HF
    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
        "x-wait-for-model": "true" # Ключевой заголовок: заставляет HF ждать загрузки
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            logging.info(f">>> ЗАПРОС К МОДЕЛИ: {model_id}")
            async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
                status = resp.status
                
                if status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    
                    if isinstance(data, list):
                        txt = data[0].get('generated_text', '')
                    else:
                        txt = data.get('generated_text', '')
                    
                    # Чистка от мусора
                    tags = ["assistant", "[INST]", "[/INST]", "system", "user", "<|begin_of_text|>", "<|eot_id|>", "<|start_header_id|>", "<|end_header_id|>"]
                    for tag in tags: txt = txt.replace(tag, "")
                    return txt.strip()
                
                # ОТЛАДКА ПРИ ОШИБКЕ
                err_body = await resp.text()
                logging.error(f"!!! HF DEBUG: Status {status} | Model: {model_id} | Body: {err_body}")
                
                if status == 404:
                    return f"❌ ОШИБКА 404: Модель {model_id} не найдена. Проверь написание в коде."
                if status == 401:
                    return "❌ ОШИБКА 401: Твой HF_TOKEN не подходит. Проверь его в Render."
                if status == 403:
                    return f"❌ ОШИБКА 403: Нет доступа к {model_id}. Нужно нажать Agree на Hugging Face."
                if status == 503:
                    return "⏳ МОДЕЛЬ ПРОСЫПАЕТСЯ: Сервер загружает веса. Повтори через 20 секунд."
                
                return f"⚠️ ОШИБКА {status}: {err_body[:150]}"
        except Exception as e:
            logging.error(f"!!! NETWORK ERROR: {e}")
            return f"🔌 ОШИБКА СЕТИ: {str(e)}"

@dp.message(Command("start"))
async def start(m: Message):
    user_config[m.from_user.id] = {"mode": "chat", "text_model": "Llama 3 (Meta)", "img_model": "SD 3.5 Large"}
    await m.answer("VREONEBRO СИСТЕМА ОНЛАЙН.\n\nВыбери режим или модель кнопками ниже.", reply_markup=get_main_kb())

@dp.message(F.text == "ВЫБОР МОДЕЛЕЙ")
async def set_t(m: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=n)] for n in MODELS["text"].keys()], resize_keyboard=True)
    await m.answer("Выбери текстовый движок:", reply_markup=kb)

@dp.message(F.text == "ВЫБОР ХУДОЖНИКОВ")
async def set_i(m: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=n)] for n in MODELS["image"].keys()], resize_keyboard=True)
    await m.answer("Выбери модель генерации:", reply_markup=kb)

@dp.message(F.text.in_(list(MODELS["text"].keys()) + list(MODELS["image"].keys())))
async def save_mod(m: Message):
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Llama 3 (Meta)", "img_model": "SD 3.5 Large"}
    if m.text in MODELS["text"]: user_config[uid]["text_model"] = m.text
    else: user_config[uid]["img_model"] = m.text
    await m.answer(f"АКТИВИРОВАНО: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text == "РЕЖИМ: ЧАТ")
async def m_c(m: Message): 
    user_config[m.from_user.id]["mode"] = "chat"
    await m.answer("РЕЖИМ ЧАТА ВКЛЮЧЕН")

@dp.message(F.text == "РЕЖИМ: ФОТО")
async def m_p(m: Message): 
    user_config[m.from_user.id]["mode"] = "image"
    await m.answer("РЕЖИМ ФОТО ВКЛЮЧЕН (Промпты на английском)")

@dp.message(F.text)
async def handle(m: Message):
    if m.text in ["ВЫБОР МОДЕЛЕЙ", "ВЫБОР ХУДОЖНИКОВ", "РЕЖИМ: ЧАТ", "РЕЖИМ: ФОТО"]: return
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Llama 3 (Meta)", "img_model": "SD 3.5 Large"}
    conf = user_config[uid]
    
    if conf["mode"] == "image":
        wait_msg = await m.answer(f"<code>РИСУЮ ЧЕРЕЗ {conf['img_model']}...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["image"][conf["img_model"]], {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="vreonebro.jpg"))
            await wait_msg.delete()
        else:
            await wait_msg.edit_text(res)
    else:
        wait_msg = await m.answer(f"<code>ДУМАЮ ЧЕРЕЗ {conf['text_model']}...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["text"][conf["text_model"]], {"inputs": m.text, "parameters": {"max_new_tokens": 500, "return_full_text": False}})
        await wait_msg.edit_text(res)

async def main():
    asyncio.create_task(start_server())
    logging.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
