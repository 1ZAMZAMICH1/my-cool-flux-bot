import os
import asyncio
import aiohttp
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiohttp import web

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# ТОЛЬКО ТЕ, ЧТО РАБОТАЮТ БЕЗ ПОДТВЕРЖДЕНИЯ (ИЛИ САМЫЕ СТАБИЛЬНЫЕ)
MODELS = {
    "text": {
        "Qwen 2.5 (Public)": "Qwen/Qwen2.5-72B-Instruct",
        "DeepSeek R1": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "Microsoft Phi": "microsoft/Phi-3.5-mini-instruct"
    },
    "image": {
        "FLUX.1 (Base)": "black-forest-labs/FLUX.1-schnell",
        "Stable Diffusion XL": "stabilityai/stable-diffusion-xl-base-1.0",
        "OpenJourney": "prompthero/openjourney"
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
    # Пытаемся через новый РОУТЕР - это сейчас стандарт
    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=60) as resp:
                status = resp.status
                body = await resp.text() # Читаем полный ответ ошибки
                
                if status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    txt = data[0]['generated_text'] if isinstance(data, list) else data.get('generated_text', '')
                    return txt.split("assistant\n")[-1].strip()
                
                # Если ошибка - пишем её в лог
                logging.error(f"HF ERROR [{model_id}]: {status} - {body}")
                return f"ERR_{status}: {body[:50]}..." 
        except Exception as e:
            return f"EXC: {e}"

@dp.message(Command("start"))
async def start(m: Message):
    user_config[m.from_user.id] = {"mode": "chat", "text_model": "Qwen 2.5 (Public)", "img_model": "FLUX.1 (Base)"}
    await m.answer("VREONEBRO СИСТЕМА ЗАПУЩЕНА.\nВыбирай инструмент и работай.", reply_markup=get_main_kb())

@dp.message(F.text == "ВЫБОР МОДЕЛЕЙ")
async def set_t(m: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=n)] for n in MODELS["text"].keys()], resize_keyboard=True)
    await m.answer("Выбери текстовый движок:", reply_markup=kb)

@dp.message(F.text == "ВЫБОР ХУДОЖНИКОВ")
async def set_i(m: Message):
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=n)] for n in MODELS["image"].keys()], resize_keyboard=True)
    await m.answer("Выбери модель фото:", reply_markup=kb)

@dp.message(F.text.in_(list(MODELS["text"].keys()) + list(MODELS["image"].keys())))
async def save_mod(m: Message):
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Qwen 2.5 (Public)", "img_model": "FLUX.1 (Base)"}
    
    if m.text in MODELS["text"]: user_config[uid]["text_model"] = m.text
    else: user_config[uid]["img_model"] = m.text
    await m.answer(f"УСТАНОВЛЕНО: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text == "РЕЖИМ: ЧАТ")
async def m_c(m: Message): 
    user_config[m.from_user.id]["mode"] = "chat"
    await m.answer("РЕЖИМ: ЧАТ")

@dp.message(F.text == "РЕЖИМ: ФОТО")
async def m_p(m: Message): 
    user_config[m.from_user.id]["mode"] = "image"
    await m.answer("РЕЖИМ: ФОТО (English)")

@dp.message(F.text)
async def handle(m: Message):
    if m.text in ["ВЫБОР МОДЕЛЕЙ", "ВЫБОР ХУДОЖНИКОВ", "РЕЖИМ: ЧАТ", "РЕЖИМ: ФОТО"]: return
    conf = user_config.get(m.from_user.id, {"mode": "chat", "text_model": "Qwen 2.5 (Public)", "img_model": "FLUX.1 (Base)"})
    
    if conf["mode"] == "image":
        st = await m.answer("<code>GENERATING...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["image"][conf["img_model"]], {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="i.jpg"))
            await st.delete()
        else: await st.edit_text(f"ОШИБКА: {res}")
    else:
        st = await m.answer("<code>THINKING...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["text"][conf["text_model"]], {"inputs": m.text, "parameters": {"max_new_tokens": 500}})
        await st.edit_text(res)

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
