import os
import json
import re
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import uvicorn

# ================== AYARLAR ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")
PORT = int(os.environ.get("PORT", 10000))

if not BOT_TOKEN or not BASE_URL:
    raise RuntimeError("BOT_TOKEN veya BASE_URL eksik!")

DATA_DIR = "datasets"
META_FILE = f"{DATA_DIR}/meta.json"
MAX_RESULTS = 50

os.makedirs(DATA_DIR, exist_ok=True)

# ================== YARDIMCI ==================
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
async def home():
    return {
        "status": "aktif",
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

    return FileResponse(tmp.name, filename="sonuclar.txt", media_type="text/plain")

# ================== TELEGRAM BOT ==================
application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👑 LORD SYSTEM 👑\n\n"
        f"Dosya gönder → API oluşsun\n\n"
        f"{BASE_URL}/search/dosya?q=kelime"
    )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        return

    doc = update.message.document
    original_name = doc.file_name
    name = clean(os.path.splitext(original_name)[0])
    extension = os.path.splitext(original_name)[1]
    path = f"{DATA_DIR}/{name}{extension}"

    msg = await update.message.reply_text("📥 Yükleniyor: %0")

    last = {"p": 0}

    async def progress(current, total):
        percent = int(current * 100 / total)
        if percent % 5 == 0 and percent != last["p"]:
            last["p"] = percent
            try:
                await msg.edit_text(f"📥 Yükleniyor: %{percent}")
            except:
                pass

    file = await doc.get_file()
    await file.download_to_drive(
        custom_path=path,
        progress_callback=progress
    )

    meta[name] = {
        "path": path,
        "original_name": original_name
    }
    save_meta(meta)

    api_url = f"{BASE_URL}/search/{name}?q=test"
    await msg.edit_text(
        f"✅ **Yükleme Tamamlandı (%100)**\n\n"
        f"📂 {original_name}\n"
        f"🔗 API:\n{api_url}",
        parse_mode="Markdown"
    )

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.ALL, file_handler))

# ================== WEBHOOK ==================
@app.on_event("startup")
async def startup():
    await application.initialize()
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.bot.set_webhook(f"{BASE_URL}/telegram")

@app.post("/telegram")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    if update:
        await application.process_update(update)
    return {"ok": True}

@app.on_event("shutdown")
async def shutdown():
    await application.stop()
    await application.shutdown()

# ================== RUN ==================
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
