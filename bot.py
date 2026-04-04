import os
import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# ПЕРЕМЕННЫЕ
TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ТВОЙ НАБОР (ТОЛЬКО ТО, ЧТО ОДОБРИЛИ + ПРОВЕРЕННОЕ)
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

async def handle_hc(r): return web.Response(text="VREONEBRO_LIVE")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="ВЫБОР МОДЕЛЕЙ"), KeyboardButton(text="ВЫБОР ХУДОЖНИКОВ")],
        [KeyboardButton(text="РЕЖИМ: ЧАТ"), KeyboardButton(text="РЕЖИМ: ФОТО")]
    ], resize_keyboard=True)

async def call_hf_api(model_id, payload, is_chat=True):
    # ФИКС 410: Прямой адрес роутера Hugging Face
    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
                if resp.status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    
                    # Извлекаем текст (он может быть в разном формате у разных моделей)
                    if isinstance(data, list):
                        txt = data[0].get('generated_text', '')
                    else:
                        txt = data.get('generated_text', '')
                    
                    # ГЛУБОКАЯ ЧИСТКА ТЕГОВ (Llama, Gemma, Mistral)
                    tags = [
                        "assistant", "[INST]", "[/INST]", "system", "user",
                        "<|begin_of_text|>", "<|eot_id|>", "<|start_header_id|>", 
                        "<|end_header_id|>", "<|article|>", "<|response|>"
                    ]
                    for tag in tags:
                        txt = txt.replace(tag, "")
                    return txt.strip()
                
                err_text = await resp.text()
                logging.error(f"HF ERROR [{model_id}]: {resp.status} - {err_text}")
                return f"ОШИБКА {resp.status}: Модель просыпается или перегружена. Повтори через 10 сек."
        except Exception as e:
            return f"ОШИБКА СЕТИ: {str(e)}"

@dp.message(Command("start"))
async def start(m: Message):
    user_config[m.from_user.id] = {"mode": "chat", "text_model": "Gemma 2 (Google)", "img_model": "SD 3.5 Large"}
    await m.answer("VREONEBRO СИСТЕМА ПЕРЕЗАПУЩЕНА.\nРоутер настроен. Доступы в норме.", reply_markup=get_main_kb())

@dp.message(F.text == "ВЫБОР МОДЕЛЕЙ")
async def set_t(m: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=n)] for n in MODELS["text"].keys()], resize_keyboard=True)
    await m.answer("Выбери интеллект:", reply_markup=kb)

@dp.message(F.text == "ВЫБОР ХУДОЖНИКОВ")
async def set_i(m: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=n)] for n in MODELS["image"].keys()], resize_keyboard=True)
    await m.answer("Выбери художника:", reply_markup=kb)

@dp.message(F.text.in_(list(MODELS["text"].keys()) + list(MODELS["image"].keys())))
async def save_mod(m: Message):
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Gemma 2 (Google)", "img_model": "SD 3.5 Large"}
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
    await m.answer("РЕЖИМ ГЕНЕРАЦИИ (Промпты на англ.)")

@dp.message(F.text)
async def handle(m: Message):
    if m.text in ["ВЫБОР МОДЕЛЕЙ", "ВЫБОР ХУДОЖНИКОВ", "РЕЖИМ: ЧАТ", "РЕЖИМ: ФОТО"]: return
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Gemma 2 (Google)", "img_model": "SD 3.5 Large"}
    conf = user_config[uid]
    
    if conf["mode"] == "image":
        wait = await m.answer("<code>РИСУЮ...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["image"][conf["img_model"]], {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="vreonebro.jpg"))
            await wait.delete()
        else: await wait.edit_text(res)
    else:
        wait = await m.answer("<code>ДУМАЮ...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["text"][conf["text_model"]], {"inputs": m.text, "parameters": {"max_new_tokens": 800, "return_full_text": False}})
        await wait.edit_text(res)

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
