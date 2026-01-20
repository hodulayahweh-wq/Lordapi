import os
import math
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== ENV ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")

# ================== FASTAPI ==================
app = FastAPI()

# ================== TELEGRAM APP ==================
application = Application.builder().token(BOT_TOKEN).build()

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Bot aktif\n\n📁 Dosya gönder, yükleme % ilerleme gözüksün."
    )

# ================== DOSYA YÜKLEME ==================
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("📤 Yükleme başlıyor... %0")

    file = None
    size = 0

    if update.message.document:
        file = update.message.document
        size = file.file_size
    elif update.message.video:
        file = update.message.video
        size = file.file_size
    elif update.message.audio:
        file = update.message.audio
        size = file.file_size
    else:
        await msg.edit_text("❌ Desteklenmeyen dosya")
        return

    tg_file = await context.bot.get_file(file.file_id)

    downloaded = 0
    last_percent = 0

    async for chunk in tg_file.iter_download():
        downloaded += len(chunk)
        percent = math.floor((downloaded / size) * 100)

        if percent >= last_percent + 5:
            last_percent = percent
            await msg.edit_text(f"📤 Yükleniyor... %{percent}")

    await msg.edit_text("✅ Yükleme tamamlandı")

# ================== HANDLERS ==================
application.add_handler(CommandHandler("start", start))
application.add_handler(
    MessageHandler(
        filters.Document.ALL | filters.Video.ALL | filters.Audio.ALL,
        handle_file
    )
)

# ================== WEBHOOK ==================
@app.on_event("startup")
async def startup():
    await application.bot.set_webhook(f"{BASE_URL}/webhook")
    print("Webhook ayarlandı")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
