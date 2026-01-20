import os import re import json import threading import tempfile

from fastapi import FastAPI, HTTPException from fastapi.responses import FileResponse from telegram import Update from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN") BASE_URL = os.getenv("BASE_URL") PORT = int(os.getenv("PORT", "8000"))

DATA_DIR = "datasets" META_FILE = "datasets/meta.json" MAX_JSON_RESULTS = 50

os.makedirs(DATA_DIR, exist_ok=True)

def clean_name(name): name = name.lower() name = re.sub(r"[^a-z0-9_-]", "", name) return name

def load_meta(): if not os.path.exists(META_FILE): return {} with open(META_FILE, "r", encoding="utf-8") as f: return json.load(f)

def save_meta(meta): with open(META_FILE, "w", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=2)

meta = load_meta()

app = FastAPI()

@app.get("/") def root(): return {"status": "ok", "datasets": list(meta.keys())}

@app.get("/search/{dataset}") def search(dataset: str, q: str): dataset = clean_name(dataset)

if dataset not in meta:
    raise HTTPException(404, "dataset yok")

if not meta[dataset]["active"]:
    raise HTTPException(403, "dataset kapalı")

path = meta[dataset]["path"]
query = q.lower()
results = []

with open(path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if query in line.lower():
            results.append(line.strip())

if len(results) <= MAX_JSON_RESULTS:
    return {
        "dataset": dataset,
        "query": query,
        "count": len(results),
        "results": results
    }

tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
with open(tmp.name, "w", encoding="utf-8") as out:
    for r in results:
        out.write(r + "\n")

return FileResponse(
    tmp.name,
    filename=f"{dataset}_results.txt",
    media_type="text/plain"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text( "Dosya gönder → API oluşur\n" "Örnek: /search/rehber?q=ali" )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE): doc = update.message.document raw = os.path.splitext(doc.file_name)[0] name = clean_name(raw)

file = await doc.get_file()
path = os.path.join(DATA_DIR, name + ".txt")
await file.download_to_drive(path)

meta[name] = {
    "path": path,
    "active": True
}

save_meta(meta)

await update.message.reply_text(
    "API hazır:\n" + BASE_URL + "/search/" + name + "?q=kelime"
)

async def listele(update: Update, context: ContextTypes.DEFAULT_TYPE): if not meta: await update.message.reply_text("Dataset yok") return

text = "API Listesi:\n"
for k in meta:
    state = "acik" if meta[k]["active"] else "kapali"
    text += k + " (" + state + ")\n"

await update.message.reply_text(text)

async def kapat(update: Update, context: ContextTypes.DEFAULT_TYPE): name = clean_name(" ".join(context.args)) if name in meta: meta[name]["active"] = False save_meta(meta) await update.message.reply_text(name + " kapatildi") else: await update.message.reply_text("Yok")

async def ac(update: Update, context: ContextTypes.DEFAULT_TYPE): name = clean_name(" ".join(context.args)) if name in meta: meta[name]["active"] = True save_meta(meta) await update.message.reply_text(name + " acildi") else: await update.message.reply_text("Yok")

async def sil(update: Update, context: ContextTypes.DEFAULT_TYPE): name = clean_name(" ".join(context.args)) if name in meta: try: os.remove(meta[name]["path"]) except Exception: pass del meta[name] save_meta(meta) await update.message.reply_text(name + " silindi") else: await update.message.reply_text("Yok")

async def run_bot(): tg = Application.builder().token(BOT_TOKEN).build()

tg.add_handler(CommandHandler("start", start))
tg.add_handler(CommandHandler("listele", listele))
tg.add_handler(CommandHandler("kapat", kapat))
tg.add_handler(CommandHandler("ac", ac))
tg.add_handler(CommandHandler("sil", sil))
tg.add_handler(MessageHandler(filters.Document.ALL, handle_file))

if BASE_URL:
    await tg.bot.set_webhook(BASE_URL + "/telegram")
    await tg.initialize()
    await tg.start()
else:
    await tg.run_polling()

def start_bot(): import asyncio asyncio.run(run_bot())

if name == "main": t = threading.Thread(target=start_bot, daemon=True) t.start()

import uvicorn
uvicorn.run(app, host="0.0.0.0", port=PORT)
