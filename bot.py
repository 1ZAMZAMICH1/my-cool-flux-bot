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

LOGO = """
<code>
 V R E O N E B R O [v2.0]
 _________________________
|  _____________________  |
| | SYSTEM: ONLINE      | |
| | CORES:  ACTIVE      | |
| | MODELS: EXPANDED    | |
| |_____________________| |
|_________________________|
    |_________________|
</code>
"""

MODELS = {
    "text": {
        "Qwen 2.5 72B": "Qwen/Qwen2.5-72B-Instruct",
        "DeepSeek R1": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        "Mistral Nemo": "mistralai/Mistral-Nemo-Instruct-2407",
        "Llama 3.2 3B": "meta-llama/Llama-3.2-3B-Instruct",
        "Gemma 2 9B": "google/gemma-2-9b-it",
        "Phi 3.5 Mini": "microsoft/Phi-3.5-mini-instruct",
        "Hermes 3": "NousResearch/Hermes-3-Llama-3.1-8B",
        "Zephyr 7B": "HuggingFaceH4/zephyr-7b-beta",
        "Yi 1.5 34B": "01-ai/Yi-1.5-34B-Chat",
        "Aya 23 (8B)": "CohereForAI/aya-23-8B"
    },
    "image": {
        "FLUX.1 Schnell": "black-forest-labs/FLUX.1-schnell",
        "SDXL 1.0": "stabilityai/stable-diffusion-xl-base-1.0",
        "SD 3.5 Large": "stabilityai/stable-diffusion-3.5-large",
        "OpenJourney v4": "prompthero/openjourney",
        "Realistic V6": "SG161222/Realistic_Vision_V6.0_B1_noVAE",
        "SDXL Lightning": "ByteDance/SDXL-Lightning",
        "Dreamlike Photo": "dreamlike-art/dreamlike-photoreal-2.0",
        "Kandinsky 2.2": "kandinsky-community/kandinsky-2.2-decoder",
        "Anime Style": "Linaqruf/anything-v5.0",
        "Cyberpunk": "DGSpitzer/Cyberpunk-Anime-Diffusion"
    }
}

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_config = {}

async def handle_hc(r): return web.Response(text="VREONEBRO_V2_RUNNING")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000))).start()

def get_main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🧠 МОЗГИ"), KeyboardButton(text="🖌 КИСТИ")],
        [KeyboardButton(text="[ РЕЖИМ: ЧАТ ]"), KeyboardButton(text="[ РЕЖИМ: ФОТО ]")]
    ], resize_keyboard=True)

def get_model_kb(m_type):
    names = list(MODELS[m_type].keys())
    buttons = [[KeyboardButton(text=names[i]), KeyboardButton(text=names[i+1])] for i in range(0, len(names)-1, 2)]
    if len(names) % 2 != 0: buttons.append([KeyboardButton(text=names[-1])])
    buttons.append([KeyboardButton(text="ВЕРНУТЬСЯ")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def call_hf_api(model_id, payload, is_chat=True):
    url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=120) as resp:
                if resp.status == 200:
                    if not is_chat: return await resp.read()
                    data = await resp.json()
                    txt = data[0]['generated_text'] if isinstance(data, list) else data.get('generated_text', '')
                    for tag in ["<|assistant|>", "assistant\n", "[/INST]", "<|res|>", "GPT4 Correct Assistant:", "Response:"]:
                        if tag in txt: txt = txt.split(tag)[-1]
                    return txt.strip()
                return f"ERROR_{resp.status}"
        except Exception as e: return f"EXC: {e}"

@dp.message(Command("start"))
async def start(m: Message):
    user_config[m.from_user.id] = {"mode": "chat", "text_model": "Qwen 2.5 72B", "img_model": "FLUX.1 Schnell"}
    await m.answer(f"{LOGO}\nVREONEBRO: Система готова. Выбери инструменты.", 
                   parse_mode="HTML", reply_markup=get_main_kb())

@dp.message(F.text == "ВЕРНУТЬСЯ")
async def back(m: Message): await m.answer("ГЛАВНОЕ МЕНЮ", reply_markup=get_main_kb())

@dp.message(F.text == "🧠 МОЗГИ")
async def set_t(m: Message): await m.answer("ДОСТУПНЫЕ LLM:", reply_markup=get_model_kb("text"))

@dp.message(F.text == "🖌 КИСТИ")
async def set_i(m: Message): await m.answer("ДОСТУПНЫЕ ГЕНЕРАТОРЫ:", reply_markup=get_model_kb("image"))

@dp.message(F.text.in_(MODELS["text"].keys()))
async def save_t(m: Message):
    user_config[m.from_user.id]["text_model"] = m.text
    await m.answer(f"ВКЛЮЧЕНО: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text.in_(MODELS["image"].keys()))
async def save_i(m: Message):
    user_config[m.from_user.id]["img_model"] = m.text
    await m.answer(f"ВКЛЮЧЕНО: {m.text}", reply_markup=get_main_kb())

@dp.message(F.text == "[ РЕЖИМ: ЧАТ ]")
async def m_c(m: Message):
    user_config[m.from_user.id]["mode"] = "chat"
    await m.answer("РЕЖИМ: ЧАТ")

@dp.message(F.text == "[ РЕЖИМ: ФОТО ]")
async def m_p(m: Message):
    user_config[m.from_user.id]["mode"] = "image"
    await m.answer("РЕЖИМ: ФОТО (English)")

@dp.message(F.text)
async def handle(m: Message):
    if m.text in ["🧠 МОЗГИ", "🖌 КИСТИ", "[ РЕЖИМ: ЧАТ ]", "[ РЕЖИМ: ФОТО ]", "ВЕРНУТЬСЯ"]: return
    conf = user_config.get(m.from_user.id, {"mode": "chat", "text_model": "Qwen 2.5 72B", "img_model": "FLUX.1 Schnell"})
    
    if conf["mode"] == "image":
        status = await m.answer("<code>LOADING_PIXELS...</code>", parse_mode="HTML")
        res = await call_hf_api(MODELS["image"][conf["img_model"]], {"inputs": m.text}, is_chat=False)
        if isinstance(res, bytes):
            await m.answer_photo(BufferedInputFile(res, filename="i.jpg"), caption=f"BY {conf['img_model']}")
            await status.delete()
        else: await status.edit_text(f"FAIL: {res}")
    else:
        status = await m.answer("<code>THINKING...</code>", parse_mode="HTML")
        model_id = MODELS["text"][conf["text_model"]]
        payload = {"inputs": f"{m.text}", "parameters": {"max_new_tokens": 1000, "return_full_text": False}}
        res = await call_hf_api(model_id, payload)
        await status.edit_text(f"<b>[{conf['text_model']}]</b>\n\n{res}", parse_mode="HTML")

async def main():
    asyncio.create_task(start_server())
    await dp.start_polling(bot)

if __name__ == "__main__": asyncio.run(main())
