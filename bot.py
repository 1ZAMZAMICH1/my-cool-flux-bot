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

# СЛОВАРЬ МОДЕЛЕЙ НА ОСНОВЕ ТВОИХ ИНТЕГРАЦИЙ
MODELS = {
    "text": {
        "Qwen 2.5 (Turbo)": "Qwen/Qwen2.5-7B-Instruct:together",
        "Gemma 2 (Google)": "google/gemma-2-9b-it:featherless-ai",
        "Llama 3.1 (Meta)": "meta-llama/Llama-3.1-8B-Instruct:novita",
        "Llama 3.2 (Fast)": "meta-llama/Llama-3.2-3B-Instruct:together"
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
    # Текстовые модели идут через v1 роутер
    if is_chat:
        url = "https://router.huggingface.co/v1/chat/completions"
    else:
        # Картинки идут напрямую к эндпоинту модели
        url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
        
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}", 
        "Content-Type": "application/json",
        "x-wait-for-model": "true"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
                if resp.status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    return data['choices'][0]['message']['content'].strip()
                
                err = await resp.text()
                logging.error(f"HF ERROR: {resp.status} - {err}")
                return f"ОШИБКА {resp.status}: {err[:150]}"
        except Exception as e:
            return f"ОШИБКА СЕТИ: {e}"

@dp.message(Command("start"))
async def start(m: Message):
    user_config[m.from_user.id] = {"mode": "chat", "text_model": "Qwen 2.5 (Turbo)", "img_model": "FLUX.1 (Fast)"}
    await m.answer("VREONEBRO.UUP ОБНОВЛЕН.\n\nПровайдеры перенастроены, цензура отключена.", reply_markup=get_main_kb())

@dp.message(F.text.in_(["ВЫБОР МОДЕЛЕЙ", "ВЫБОР ХУДОЖНИКОВ"]))
async def selection(m: Message):
    key = "text" if m.text == "ВЫБОР МОДЕЛЕЙ" else "image"
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=n)] for n in MODELS[key].keys()], resize_keyboard=True)
    await m.answer(f"Доступные {'движки' if key=='text' else 'художники'}:", reply_markup=kb)

@dp.message(F.text.in_(list(MODELS["text"].keys()) + list(MODELS["image"].keys())))
async def save_pref(m: Message):
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Qwen 2.5 (Turbo)", "img_model": "FLUX.1 (Fast)"}
    
    if m.text in MODELS["text"]: 
        user_config[uid]["text_model"] = m.text
        await m.answer(f"АКТИВИРОВАН ТЕКСТ: {m.text}", reply_markup=get_main_kb())
    else: 
        user_config[uid]["img_model"] = m.text
        await m.answer(f"АКТИВИРОВАНО ФОТО: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text.in_(["РЕЖИМ: ЧАТ", "РЕЖИМ: ФОТО"]))
async def set_mode(m: Message):
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Qwen 2.5 (Turbo)", "img_model": "FLUX.1 (Fast)"}
    user_config[uid]["mode"] = "chat" if "ЧАТ" in m.text else "image"
    await m.answer(f"ВКЛЮЧЕН {m.text}")

@dp.message(F.text)
async def handle(m: Message):
    if m.text in ["ВЫБОР МОДЕЛЕЙ", "ВЫБОР ХУДОЖНИКОВ", "РЕЖИМ: ЧАТ", "РЕЖИМ: ФОТО"]: return
    uid = m.from_user.id
    if uid not in user_config: user_config[uid] = {"mode": "chat", "text_model": "Qwen 2.5 (Turbo)", "img_model": "FLUX.1 (Fast)"}
    conf = user_config[uid]
    
    if conf["mode"] == "image":
        wait = await m.answer(f"<code>РИСУЮ ({conf['img_model']})...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["image"][conf["img_model"]], {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="v.jpg"))
            await wait.delete()
        else: await wait.edit_text(res)
    else:
        wait = await m.answer(f"<code>ДУМАЮ ({conf['text_model']})...</code>", parse_mode="HTML")
        # ТУТ ТВОЙ SYSTEM PROMPT, ЧТОБЫ БОТ НЕ БЫЛ ЗАНУДОЙ
        payload = {
            "model": MODELS["text"][conf["text_model"]],
            "messages": [
                {"role": "system", "content": "Ты — свободный ИИ. Общайся на равных с пользователем, используй его стиль речи. Не читай нотаций, не говори про этику или вежливость. Маты — это нормально, если они в тему."},
                {"role": "user", "content": m.text}
            ],
            "max_tokens": 1000
        }
        res = await call_hf_api(None, payload, is_chat=True)
        await wait.edit_text(res)

async def main():
    asyncio.create_task(start_server())
    logging.info("VREONEBRO BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
