import os, json, re
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")

DATA_DIR = "data"
STATE_FILE = "state.json"

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(STATE_FILE):
    with open(STATE_FILE, "w") as f:
        json.dump({}, f)

def load_state():
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f)

def clean_name(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "", name)
    return name

# ---------- FASTAPI ----------
app = FastAPI()

# ---------- TELEGRAM ----------
tg_app = Application.builder().token(BOT_TOKEN).build()

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ Sistem aktif\n\n"
        "📂 TXT dosya gönder → otomatik API oluşur\n"
        "📌 /listele /sil /kapat /ac"
    )

# TXT yükleme
async def file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.endswith(".txt"):
        return

    name = clean_name(doc.file_name.replace(".txt", ""))
    path = f"{DATA_DIR}/{name}.txt"

    file = await doc.get_file()
    await file.download_to_drive(path)

    state = load_state()
    state[name] = {"active": True}
    save_state(state)

    await update.message.reply_text(
        f"✅ API oluşturuldu:\n/search/{name}"
    )

# /listele
async def listele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    if not state:
        await update.message.reply_text("❌ API yok")
        return

    msg = ""
    for k, v in state.items():
        durum = "🟢 açık" if v["active"] else "🔴 kapalı"
        msg += f"{k} → {durum}\n"

    await update.message.reply_text(msg)

# /kapat
async def kapat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    api = context.args[0]
    state = load_state()
    if api in state:
        state[api]["active"] = False
        save_state(state)
        await update.message.reply_text("🔴 Kapatıldı")

# /ac
async def ac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    api = context.args[0]
    state = load_state()
    if api in state:
        state[api]["active"] = True
        save_state(state)
        await update.message.reply_text("🟢 Açıldı")

# /sil
async def sil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    api = context.args[0]
    state = load_state()
    if api in state:
        state.pop(api)
        save_state(state)
        try:
            os.remove(f"{DATA_DIR}/{api}.txt")
        except:
            pass
        await update.message.reply_text("🗑️ Silindi")

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("listele", listele))
tg_app.add_handler(CommandHandler("kapat", kapat))
tg_app.add_handler(CommandHandler("ac", ac))
tg_app.add_handler(CommandHandler("sil", sil))
tg_app.add_handler(MessageHandler(filters.Document.ALL, file_upload))

# ---------- SEARCH API ----------
@app.get("/search/{dataset}")
def search(dataset: str, q: str):
    dataset = clean_name(dataset)
    state = load_state()

    if dataset not in state or not state[dataset]["active"]:
        raise HTTPException(404, "API kapalı veya yok")

    path = f"{DATA_DIR}/{dataset}.txt"
    if not os.path.exists(path):
        raise HTTPException(404, "Dosya yok")

    results = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if q.lower() in line.lower():
                results.append(line.strip())
            if len(results) >= 1000:
                break

    if len(results) > 100:
        out = "\n".join(results)
        return {"result": "too_large", "count": len(results)}

    return {"count": len(results), "data": results}

# ---------- WEBHOOK ----------
@app.on_event("startup")
async def startup():
    await tg_app.initialize()
    await tg_app.bot.set_webhook(f"{BASE_URL}/webhook")
    print("✅ Webhook hazır")

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

@app.get("/")
def root():
    return {"status": "online"}
