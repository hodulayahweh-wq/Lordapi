import os
import re
import json
import tempfile
import asyncio

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
import uvicorn

# ================= AYARLAR =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")
PORT = int(os.getenv("PORT", "10000"))

DATA_DIR = "datasets"
META_FILE = "datasets/meta.json"
MAX_JSON_RESULTS = 50

os.makedirs(DATA_DIR, exist_ok=True)

# ================= YARDIMCI =================

def clean_name(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9_-]", "", name)
    return name

def load_meta():
    if not os.path.exists(META_FILE):
        return {}
    with open(META_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_meta(meta):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

meta = load_meta()

# ================= FASTAPI =================

app = FastAPI()

@app.get("/")
def root():
    return {
        "status": "ok",
        "datasets": list(meta.keys())
    }

@app.get("/search/{dataset}")
def search(dataset: str, q: str):
    dataset = clean_name(dataset)

    if dataset not in meta:
        raise HTTPException(404, "Dataset yok")

    if not meta[dataset]["active"]:
        raise HTTPException(403, "Dataset kapalı")

    results = []
    path = meta[dataset]["path"]

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if q.lower() in line.lower():
                results.append(line.strip())

    if len(results) <= MAX_JSON_RESULTS:
        return {
            "dataset": dataset,
            "query": q,
            "count": len(results),
            "results": results
        }

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    with open(tmp.name, "w", encoding="utf-8") as out:
        for r in results:
            out.write(r + "\n")

    return FileResponse(
        tmp.name,
        filename=f"{dataset}_sonuc.txt",
        media_type="text/plain"
    )

# ================= TELEGRAM =================

tg_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 TXT dosya gönder → otomatik API oluşur\n\n"
        "🔎 Örnek:\n"
        "/search/rehber?q=ali\n\n"
        "/listele → API listesi"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    raw = os.path.splitext(doc.file_name)[0]
    name = clean_name(raw)

    path = os.path.join(DATA_DIR, name + ".txt")

    file = await doc.get_file()
    await file.download_to_drive(path)

    meta[name] = {
        "path": path,
        "active": True
    }
    save_meta(meta)

    await update.message.reply_text(
        "✅ API hazır:\n"
        f"{BASE_URL}/search/{name}?q=kelime"
    )

async def listele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not meta:
        await update.message.reply_text("Hiç dataset yok")
        return

    text = "📊 API Listesi:\n"
    for k in meta:
        durum = "açık" if meta[k]["active"] else "kapalı"
        text += f"- {k} ({durum})\n"

    await update.message.reply_text(text)

async def kapat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = clean_name(" ".join(context.args))
    if name in meta:
        meta[name]["active"] = False
        save_meta(meta)
        await update.message.reply_text(f"{name} kapatıldı")
    else:
        await update.message.reply_text("Bulunamadı")

async def ac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = clean_name(" ".join(context.args))
    if name in meta:
        meta[name]["active"] = True
        save_meta(meta)
        await update.message.reply_text(f"{name} açıldı")
    else:
        await update.message.reply_text("Bulunamadı")

async def sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = clean_name(" ".join(context.args))
    if name in meta:
        try:
            os.remove(meta[name]["path"])
        except:
            pass
        del meta[name]
        save_meta(meta)
        await update.message.reply_text(f"{name} silindi")
    else:
        await update.message.reply_text("Bulunamadı")

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("listele", listele))
tg_app.add_handler(CommandHandler("kapat", kapat))
tg_app.add_handler(CommandHandler("ac", ac))
tg_app.add_handler(CommandHandler("sil", sil))
tg_app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

# ================= WEBHOOK =================

@app.on_event("startup")
async def on_startup():
    await tg_app.initialize()
    await tg_app.bot.set_webhook(BASE_URL + "/telegram")
    await tg_app.start()

@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

# ================= RUN =================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
