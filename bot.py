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

# ЛОГОТИП VREONEBRO
LOGO = "<code>\n V R E O N E B R O\n _________________\n|  _____________  |\n| |             | |\n| |   SYSTEM    | |\n| |    READY    | |\n| |_____________| |\n|_________________|\n    |_________|\n     _________\n    |_________|\n</code>"

# НОВЫЙ ФОРМАТ ССЫЛОК (API 2026)
MODELS = {
    "text": {
        "Mistral 7B": "mistralai/Mistral-7B-v0.3",
        "Qwen 2.5 72B": "Qwen/Qwen2.5-72B-Instruct",
        "Llama 3.1 8B": "meta-llama/Meta-Llama-3.1-8B-Instruct"
    },
    "image": {
        "FLUX.1": "black-forest-labs/FLUX.1-schnell",
        "SD 3.5 Large": "stabilityai/stable-diffusion-3.5-large",
        "Midjourney": "prompthero/openjourney"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_config = {}

async def handle_hc(r): return web.Response(text="SYSTEM ACTIVE")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Выбор нейросети"), KeyboardButton(text="Выбор художника")],
        [KeyboardButton(text="Режим: Чат"), KeyboardButton(text="Режим: Фото")]
    ], resize_keyboard=True)

def get_model_kb(m_type):
    buttons = [[KeyboardButton(text=name)] for name in MODELS[m_type].keys()]
    buttons.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def call_hf_api(model_id, payload, is_chat=True):
    # ПЕРЕХОД НА НОВЫЙ РОУТЕР (Фикс ошибки 410)
    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=90) as resp:
                if resp.status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    res = data[0]['generated_text'] if isinstance(data, list) else data['generated_text']
                    return res.split("assistant\n")[-1].strip()
                return f"ERROR_{resp.status}"
        except Exception as e: return f"EXC_{e}"

@dp.message(Command("start"))
async def start(m: Message):
    user_config[m.from_user.id] = {"mode": "chat", "text_model": "Mistral 7B", "img_model": "FLUX.1"}
    await m.answer(f"{LOGO}\nVREONEBRO запущен. Режимы активны. Выбирай.", parse_mode="HTML", reply_markup=get_main_kb())

@dp.message(F.text == "Назад")
async def back(m: Message): await m.answer("Меню", reply_markup=get_main_kb())

@dp.message(F.text == "Выбор нейросети")
async def set_t(m: Message): await m.answer("Модели текста:", reply_markup=get_model_kb("text"))

@dp.message(F.text == "Выбор художника")
async def set_i(m: Message): await m.answer("Модели фото:", reply_markup=get_model_kb("image"))

@dp.message(F.text.in_(MODELS["text"].keys()))
async def save_t(m: Message):
    user_config[m.from_user.id]["text_model"] = m.text
    await m.answer(f"Модель: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text.in_(MODELS["image"].keys()))
async def save_i(m: Message):
    user_config[m.from_user.id]["img_model"] = m.text
    await m.answer(f"Художник: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text == "Режим: Чат")
async def m_c(m: Message):
    user_config[m.from_user.id]["mode"] = "chat"
    await m.answer("ЧАТ АКТИВИРОВАН")

@dp.message(F.text == "Режим: Фото")
async def m_p(m: Message):
    user_config[m.from_user.id]["mode"] = "image"
    await m.answer("ФОТО АКТИВИРОВАНО")

@dp.message(F.text)
async def handle(m: Message):
    conf = user_config.get(m.from_user.id, {"mode": "chat", "text_model": "Mistral 7B", "img_model": "FLUX.1"})
    status = await m.answer("<code>PROCESSING...</code>", parse_mode="HTML")
    
    if conf["mode"] == "image":
        res = await call_hf_api(MODELS["image"][conf["img_model"]], {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="i.jpg"))
            await status.delete()
        else: await status.edit_text(f"SYSTEM_ERROR: {res}")
    else:
        model_id = MODELS["text"][conf["text_model"]]
        res = await call_hf_api(model_id, {"inputs": m.text, "parameters": {"max_new_tokens": 500}})
        await status.edit_text(f"<b>{conf['text_model']}</b>:\n{res}", parse_mode="HTML")

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
