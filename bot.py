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

# ЛОГОТИП
LOGO = """
<code>
 V R E O N E B R O
 _________________
|  _____________  |
| |             | |
| |   SYSTEM    | |
| |    READY    | |
| |_____________| |
|_________________|
    |_________|
     _________
    |_________|
</code>
"""

# РАСШИРЕННЫЙ СПИСОК МОДЕЛЕЙ
MODELS = {
    "text": {
        "Mistral 7B": "mistralai/Mistral-7B-v0.3",
        "Qwen 2.5 72B": "Qwen/Qwen2.5-72B-Instruct",
        "Llama 3.1 8B": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "Gemma 2 9B": "google/gemma-2-9b-it",
        "Phi-3 Mini": "microsoft/Phi-3-mini-4k-instruct"
    },
    "image": {
        "FLUX.1": "black-forest-labs/FLUX.1-schnell",
        "SD 3.5 Large": "stabilityai/stable-diffusion-3.5-large",
        "AuraFlow": "fal/AuraFlow",
        "Realistic": "SG161222/Realistic_Vision_V6.0_B1_noVAE",
        "Midjourney Style": "prompthero/openjourney"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_config = {}

async def handle_hc(r): return web.Response(text="VREONEBRO ONLINE")
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

async def call_api(model_id, payload, is_chat=True):
    url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
                if resp.status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    txt = data[0]['generated_text'] if isinstance(data, list) else data['generated_text']
                    for tag in ["[/INST]", "assistant\n", "<|assistant|>", "GPT4 Correct Assistant:", "Assistant:"]:
                        if tag in txt: txt = txt.split(tag)[-1]
                    return txt.strip()
                return f"Error {resp.status}"
        except Exception as e: return f"Exception: {e}"

@dp.message(Command("start"))
async def start(m: Message):
    user_config[m.from_user.id] = {"mode": "chat", "text_model": "Mistral 7B", "img_model": "FLUX.1"}
    await m.answer(f"{LOGO}\nVREONEBRO запущен. Текст и фото. Без лишней херни. Выбирай модель или пиши сразу.", 
                   parse_mode="HTML", reply_markup=get_main_kb())

@dp.message(F.text == "Назад")
async def back(m: Message):
    await m.answer("Главное меню", reply_markup=get_main_kb())

@dp.message(F.text == "Выбор нейросети")
async def set_t_mod(m: Message):
    await m.answer("Доступные мозги:", reply_markup=get_model_kb("text"))

@dp.message(F.text == "Выбор художника")
async def set_i_mod(m: Message):
    await m.answer("Доступные кисти:", reply_markup=get_model_kb("image"))

@dp.message(F.text.in_(MODELS["text"].keys()))
async def save_t_mod(m: Message):
    user_config[m.from_user.id]["text_model"] = m.text
    await m.answer(f"Выбрано: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text.in_(MODELS["image"].keys()))
async def save_i_mod(m: Message):
    user_config[m.from_user.id]["img_model"] = m.text
    await m.answer(f"Выбрано: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text == "Режим: Чат")
async def mode_c(m: Message):
    user_config[m.from_user.id]["mode"] = "chat"
    await m.answer("Режим: ЧАТ")

@dp.message(F.text == "Режим: Фото")
async def mode_p(m: Message):
    user_config[m.from_user.id]["mode"] = "image"
    await m.answer("Режим: ФОТО (English prompt)")

@dp.message(F.text)
async def handle(m: Message):
    conf = user_config.get(m.from_user.id, {"mode": "chat", "text_model": "Mistral 7B", "img_model": "FLUX.1"})
    
    if conf["mode"] == "image":
        status = await m.answer("<code>GENERATING...</code>", parse_mode="HTML")
        res = await call_api(MODELS["image"][conf["img_model"]], {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="i.jpg"), caption=f"Model: {conf['img_model']}")
            await status.delete()
        else: await status.edit_text(f"ERROR: {res}")
    else:
        status = await m.answer("<code>THINKING...</code>", parse_mode="HTML")
        model_id = MODELS["text"][conf["text_model"]]
        payload = {"inputs": f"{m.text}", "parameters": {"max_new_tokens": 1000}}
        res = await call_api(model_id, payload)
        await status.edit_text(f"<b>{conf['text_model']}</b>:\n\n{res}", parse_mode="HTML")

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
