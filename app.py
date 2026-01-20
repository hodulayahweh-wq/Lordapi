import os
import re
import json
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")

if not BOT_TOKEN or not BASE_URL:
    raise RuntimeError("BOT_TOKEN veya BASE_URL eksik")

DATA_DIR = "datasets"
META_FILE = f"{DATA_DIR}/meta.json"
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
        json.dump(data, f, indent=2, ensure_ascii=False)

meta = load_meta()

# ================== FASTAPI ==================
app = FastAPI(title="LORD SYSTEM")

@app.get("/")
async def root():
    return {
        "status": "aktif",
        "datasets": list(meta.keys())
    }

@app.get("/search/{dataset}")
async def search(dataset: str, q: str):
    dataset = clean(dataset)

    if dataset not in meta:
        return JSONResponse(
            {"error": "Dataset bulunamadı"},
            status_code=404
        )

    path = meta[dataset]["path"]
    results = []

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if q.lower() in line.lower():
                    results.append(line.strip())
    except Exception as e:
        return {"error": str(e)}

    if len(results) <= MAX_RESULTS:
        return {"count": len(results), "results": results}

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    tmp.write("\n".join(results))
    tmp.close()

    return FileResponse(tmp.name, filename="sonuclar.txt")

# ================== TELEGRAM ==================
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 LORD SYSTEM AKTİF 👑\n\n"
        "📁 Dosya gönder → API oluşur\n"
        "🔍 Arama: /search/dosya?q=kelime\n"
        f"🌐 Site: {BASE_URL}"
    )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("❌ Dosya gönder")
        return

    doc = update.message.document
    original = doc.file_name
    name = clean(os.path.splitext(original)[0])
    ext = os.path.splitext(original)[1]
    path = f"{DATA_DIR}/{name}{ext}"

    tg_file = await doc.get_file()
    await tg_file.download_to_drive(path)

    meta[name] = {
        "path": path,
        "original": original
    }
    save_meta(meta)

    api = f"{BASE_URL}/search/{name}?q=test"

    await update.message.reply_text(
        f"✅ Dosya yüklendi\n\n"
        f"📄 {original}\n"
        f"🔗 API:\n{api}"
    )

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

# ================== WEBHOOK ==================
@app.on_event("startup")
async def on_startup():
    await tg_app.initialize()
    await tg_app.bot.set_webhook(f"{BASE_URL}/telegram")
    print("Webhook OK")

@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

@app.on_event("shutdown")
async def on_shutdown():
    await tg_app.shutdown()
