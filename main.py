import os
import json
import re
import tempfile
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import uvicorn

# ================== AYARLAR ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")
PORT = int(os.environ.get("PORT", 10000))

if not BOT_TOKEN or not BASE_URL:
    raise RuntimeError("BOT_TOKEN veya BASE_URL environment variable eksik!")

DATA_DIR = "datasets"
META_FILE = f"{DATA_DIR}/meta.json"
MAX_RESULTS = 50

os.makedirs(DATA_DIR, exist_ok=True)

# ================== YARDIMCI FONKSIYONLAR ==================
def clean(text: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", text.lower())

def load_meta() -> dict:
    if not os.path.exists(META_FILE):
        return {}
    with open(META_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_meta(data: dict):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

meta = load_meta()

# ================== FASTAPI APP ==================
app = FastAPI(title="Telegram Dosya Arama Botu")

@app.get("/")
async def home():
    return {"status": "ok", "datasets": list(meta.keys())}

@app.get("/search/{dataset}")
async def search(dataset: str, q: str):
    dataset = clean(dataset)
    if dataset not in meta:
        return {"error": "Dataset bulunamadı"}

    path = meta[dataset]["path"]
    results = []

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if q.lower() in line.lower():
                    results.append(line.strip())
    except Exception as e:
        return {"error": f"Dosya okuma hatası: {str(e)}"}

    if len(results) <= MAX_RESULTS:
        return {"count": len(results), "results": results}

    # Büyük sonuçlar için dosya döndür
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    tmp.write("\n".join(results))
    tmp.close()

    return FileResponse(tmp.name, filename="sonuclar.txt", media_type="text/plain")

# ================== TELEGRAM BOT ==================
application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📂 TXT formatında dosya gönder → Otomatik API oluşur\n"
        "🔎 Arama: /search/dosya?q=kelime\n"
        "Örnek: https://senin-url.onrender.com/search/dosya?q=test"
    )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.document:
        await update.message.reply_text("Lütfen bir TXT dosyası gönder.")
        return

    doc = update.message.document
    if not doc.file_name.lower().endswith(('.txt', '.text')):
        await update.message.reply_text("Sadece .txt dosyaları destekleniyor.")
        return

    name = clean(os.path.splitext(doc.file_name)[0])
    path = f"{DATA_DIR}/{name}.txt"

    file = await doc.get_file()
    await file.download_to_drive(custom_path=path)

    meta[name] = {"path": path}
    save_meta(meta)

    api_url = f"{BASE_URL}/search/{name}?q=test"
    await update.message.reply_text(
        f"✅ Dosya yüklendi!\n"
        f"API hazır: {api_url}\n"
        f"Arama örneği: {api_url}"
    )

# Handler'ları ekle
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.Document.ALL, file_handler))

# ================== WEBHOOK SETUP ==================
@app.on_event("startup")
async def startup_event():
    await application.initialize()
    webhook_url = f"{BASE_URL}/telegram"
    
    # Mevcut webhook'u silip yeniden ayarla (güvenlik için)
    await application.bot.delete_webhook(drop_pending_updates=True)
    success = await application.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )
    
    if success:
        print(f"Webhook başarıyla ayarlandı: {webhook_url}")
    else:
        print("Webhook ayarı BAŞARISIZ!")

@app.on_event("shutdown")
async def shutdown_event():
    await application.stop()
    await application.shutdown()

@app.post("/telegram")
async def telegram_webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, application.bot)
        if update:
            await application.process_update(update)
        return {"ok": True}
    except Exception as e:
        print(f"Webhook hatası: {e}")
        return {"ok": False}, 500

# ================== UYGULAMAYI BAŞLAT ==================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )
