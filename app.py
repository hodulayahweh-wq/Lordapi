import os
import re
import json
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== ENV ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")

if not BOT_TOKEN or not BASE_URL:
    raise RuntimeError("BOT_TOKEN veya BASE_URL eksik")

# ================== DATA ==================
DATA_DIR = "datasets"
META_FILE = os.path.join(DATA_DIR, "meta.json")
MAX_RESULTS = 50

os.makedirs(DATA_DIR, exist_ok=True)

# ================== UTILS ==================
def clean(text: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", text.lower())

def load_meta():
    if not os.path.exists(META_FILE):
        return {}
    with open(META_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_meta(data):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

meta = load_meta()

# ================== FASTAPI ==================
app = FastAPI()

@app.get("/")
async def home():
    return {
        "status": "ok",
        "datasets": list(meta.keys())
    }

@app.get("/search/{dataset}")
async def search(dataset: str, q: str):
    dataset = clean(dataset)

    if dataset not in meta:
        return {"error": "Dataset bulunamadı"}

    path = meta[dataset]["path"]
    results = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if q.lower() in line.lower():
                results.append(line.strip())

    if len(results) <= MAX_RESULTS:
        return {"count": len(results), "results": results}

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    tmp.write("\n".join(results))
    tmp.close()

    return FileResponse(tmp.name, filename="sonuclar.txt")

# ================== TELEGRAM ==================
telegram_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 BOT AKTİF 👑\n\n"
        "📁 Dosya gönder → API oluşur\n"
        "🔍 /search/dosya?q=kelime\n"
        f"🌐 {BASE_URL}"
    )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        return

    doc = update.message.document
    original = doc.file_name

    name = clean(os.path.splitext(original)[0])
    ext = os.path.splitext(original)[1]
    path = os.path.join(DATA_DIR, f"{name}{ext}")

    tg_file = await doc.get_file()
    await tg_file.download_to_drive(path)

    meta[name] = {"path": path}
    save_meta(meta)

    await update.message.reply_text(
        f"✅ Dosya yüklendi\n\n"
        f"{BASE_URL}/search/{name}?q=test"
    )

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

# ================== WEBHOOK ==================
@app.on_event("startup")
async def startup():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(f"{BASE_URL}/telegram")
    print("Webhook set edildi")

@app.post("/telegram")
async def telegram_webhook(request: Request):
    update = Update.de_json(await request.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}

@app.on_event("shutdown")
async def shutdown():
    await telegram_app.shutdown()
