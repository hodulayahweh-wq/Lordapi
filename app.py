import os
import re
import json
import asyncio
import tempfile
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import uvicorn

# ================= AYAR =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")
PORT = int(os.environ.get("PORT", 8000))

DATA_DIR = "datasets"
META_FILE = "datasets/meta.json"
MAX_JSON = 50  # bundan fazla ise txt verir

os.makedirs(DATA_DIR, exist_ok=True)

# ================= YARDIMCI =================
def temizle(isim: str) -> str:
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

# ================= FASTAPI =================
app = FastAPI()

@app.get("/")
def ana():
    return {
        "status": "online",
        "apis": list(meta.keys())
    }

@app.get("/search/{api}")
def search(api: str, q: str):
    api = temizle(api)

    if api not in meta:
        raise HTTPException(404, "API bulunamadı")

    if not meta[api]["active"]:
        raise HTTPException(403, "API kapalı")

    yol = meta[api]["path"]
    sonuc = []

    with open(yol, "r", encoding="utf-8", errors="ignore") as f:
        for satir in f:
            if q.lower() in satir.lower():
                sonuc.append(satir.strip())

    if len(sonuc) <= MAX_JSON:
        return {"count": len(sonuc), "results": sonuc}

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    with open(tmp.name, "w", encoding="utf-8") as out:
        for s in sonuc:
            out.write(s + "\n")

    return FileResponse(tmp.name, filename=f"{api}_sonuc.txt")

# ================= TELEGRAM BOT =================
bot = Bot(BOT_TOKEN)
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 TXT gönder → otomatik API oluşur\n\n"
        "🔎 Kullanım:\n"
        "/search/rehber?q=ali\n\n"
        "Komutlar:\n"
        "/listele\n"
        "/kapat apiadi\n"
        "/ac apiadi\n"
        "/sil apiadi"
    )

async def txt_yukle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    isim = temizle(os.path.splitext(doc.file_name)[0])

    file = await doc.get_file()
    yol = os.path.join(DATA_DIR, isim + ".txt")
    await file.download_to_drive(yol)

    meta[isim] = {
        "path": yol,
        "active": True
    }
    meta_kaydet(meta)

    await update.message.reply_text(
        "✅ API oluşturuldu:\n"
        f"{BASE_URL}/search/{isim}?q=kelime"
    )

async def listele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not meta:
        await update.message.reply_text("❌ API yok")
        return
    mesaj = "📋 API Listesi:\n"
    for k, v in meta.items():
        mesaj += f"- {k} ({'açık' if v['active'] else 'kapalı'})\n"
    await update.message.reply_text(mesaj)

async def kapat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    isim = temizle(" ".join(context.args))
    if isim in meta:
        meta[isim]["active"] = False
        meta_kaydet(meta)
        await update.message.reply_text("⛔ API kapatıldı")
    else:
        await update.message.reply_text("❌ Bulunamadı")

async def ac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    isim = temizle(" ".join(context.args))
    if isim in meta:
        meta[isim]["active"] = True
        meta_kaydet(meta)
        await update.message.reply_text("✅ API açıldı")
    else:
        await update.message.reply_text("❌ Bulunamadı")

async def sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    isim = temizle(" ".join(context.args))
    if isim in meta:
        try:
            os.remove(meta[isim]["path"])
        except:
            pass
        del meta[isim]
        meta_kaydet(meta)
        await update.message.reply_text("🗑 API silindi")
    else:
        await update.message.reply_text("❌ Bulunamadı")

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("listele", listele))
tg_app.add_handler(CommandHandler("kapat", kapat))
tg_app.add_handler(CommandHandler("ac", ac))
tg_app.add_handler(CommandHandler("sil", sil))
tg_app.add_handler(MessageHandler(filters.Document.ALL, txt_yukle))

@app.post("/telegram")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, bot)
    await tg_app.process_update(update)
    return JSONResponse({"ok": True})

async def webhook_ayarla():
    await tg_app.initialize()
    await bot.set_webhook(BASE_URL + "/telegram")

# ================= MAIN =================
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(webhook_ayarla())
    uvicorn.run(app, host="0.0.0.0", port=PORT)
