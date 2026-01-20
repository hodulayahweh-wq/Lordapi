import os
import re
import json
import asyncio
import tempfile
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import uvicorn

# ================== AYAR ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")
PORT = int(os.environ.get("PORT", 8000))

DATA_DIR = "datasets"
META_FILE = "datasets/meta.json"
MAX_JSON_RESULTS = 50

os.makedirs(DATA_DIR, exist_ok=True)

# ================== YARDIMCI ==================
def temizle(isim):
    return re.sub(r"[^a-z0-9_-]", "", isim.lower())

def meta_yukle():
    if not os.path.exists(META_FILE):
        return {}
    with open(META_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def meta_kaydet(m):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)

meta = meta_yukle()

# ================== FASTAPI ==================
app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "apis": list(meta.keys())}

@app.get("/search/{api}")
def search(api: str, q: str):
    api = temizle(api)

    if api not in meta:
        raise HTTPException(404, "API yok")

    if not meta[api]["active"]:
        raise HTTPException(403, "API kapalı")

    path = meta[api]["path"]
    sonuc = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for satir in f:
            if q.lower() in satir.lower():
                sonuc.append(satir.strip())

    if len(sonuc) <= MAX_JSON_RESULTS:
        return {"count": len(sonuc), "results": sonuc}

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    with open(tmp.name, "w", encoding="utf-8") as out:
        for s in sonuc:
            out.write(s + "\n")

    return FileResponse(tmp.name, filename=f"{api}_sonuc.txt")

# ================== TELEGRAM ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "TXT gönder → otomatik API oluşur\n"
        "Örnek:\n/search/rehber?q=ali"
    )

async def dosya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    isim = temizle(os.path.splitext(doc.file_name)[0])

    file = await doc.get_file()
    yol = os.path.join(DATA_DIR, isim + ".txt")
    await file.download_to_drive(yol)

    meta[isim] = {"path": yol, "active": True}
    meta_kaydet(meta)

    await update.message.reply_text(
        "API hazır:\n"
        f"{BASE_URL}/search/{isim}?q=kelime"
    )

async def listele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not meta:
        await update.message.reply_text("API yok")
        return
    text = "API Listesi:\n"
    for k in meta:
        text += f"{k} ({'açık' if meta[k]['active'] else 'kapalı'})\n"
    await update.message.reply_text(text)

async def kapat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    isim = temizle(" ".join(context.args))
    if isim in meta:
        meta[isim]["active"] = False
        meta_kaydet(meta)
        await update.message.reply_text("Kapatıldı")
    else:
        await update.message.reply_text("Yok")

async def ac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    isim = temizle(" ".join(context.args))
    if isim in meta:
        meta[isim]["active"] = True
        meta_kaydet(meta)
        await update.message.reply_text("Açıldı")
    else:
        await update.message.reply_text("Yok")

# ================== BOT ==================
bot = Bot(BOT_TOKEN)
tg_app = Application.builder().token(BOT_TOKEN).build()

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("listele", listele))
tg_app.add_handler(CommandHandler("kapat", kapat))
tg_app.add_handler(CommandHandler("ac", ac))
tg_app.add_handler(MessageHandler(filters.Document.ALL, dosya))

@app.post("/telegram")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    await tg_app.process_update(update)
    return {"ok": True}

async def webhook_ayarla():
    await tg_app.initialize()
    await bot.set_webhook(BASE_URL + "/telegram")

# ================== MAIN ==================
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(webhook_ayarla())
    uvicorn.run(app, host="0.0.0.0", port=PORT)
