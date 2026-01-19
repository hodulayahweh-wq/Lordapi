import telebot
import os
import zipfile
import py7zr
from flask import Flask, request, jsonify

# ================= AYARLAR =================
TOKEN = "8467419515:AAFIUi4154gL4QQfwmpjaLAE-ay12O6BjD8"
BASE_URL = "https://lordv3api.onrender.com"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

DATA_FILE = "storage/data.txt"
UPLOAD_DIR = "uploads"
TEMP_DIR = "temp"

os.makedirs("storage", exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ================ WEBHOOK =================
bot.remove_webhook()
bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = telebot.types.Update.de_json(
        request.stream.read().decode("utf-8")
    )
    bot.process_new_updates([update])
    return "OK", 200

# ================ BOT =================
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "✅ LORD API FREE\n\n"
        "📂 TXT / ZIP / 7Z / JSON gönder\n"
        "🌐 API:\nhttps://lordv3api.onrender.com/api/v1/search?ara=DEGER"
    )

@bot.message_handler(content_types=["document"])
def handle_file(m):
    try:
        file_info = bot.get_file(m.document.file_id)
        data = bot.download_file(file_info.file_path)

        path = os.path.join(UPLOAD_DIR, m.document.file_name)
        with open(path, "wb") as f:
            f.write(data)

        added = 0

        def add_lines(lines):
            nonlocal added
            with open(DATA_FILE, "a", errors="ignore") as out:
                for l in lines:
                    l = l.strip()
                    if l:
                        out.write(l + "\n")
                        added += 1

        if path.endswith((".txt", ".json")):
            with open(path, "r", errors="ignore") as f:
                add_lines(f.readlines())

        elif path.endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if name.endswith(".txt"):
                        with z.open(name) as f:
                            add_lines(
                                f.read().decode(errors="ignore").splitlines()
                            )

        elif path.endswith(".7z"):
            with py7zr.SevenZipFile(path, "r") as z:
                z.extractall(TEMP_DIR)
            for root, _, files in os.walk(TEMP_DIR):
                for file in files:
                    if file.endswith(".txt"):
                        with open(os.path.join(root, file), "r", errors="ignore") as f:
                            add_lines(f.readlines())

        bot.send_message(
            m.chat.id,
            f"✅ Dosya işlendi\n📄 Eklenen satır: {added}"
        )

    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Hata: {e}")

# ================ API =================
@app.route("/")
def home():
    return "LORD SYSTEM SORGU V3"

@app.route("/api/v1/search")
def search():
    q = request.args.get("ara", "").strip()
    if not q:
        return jsonify({"error": "ara parametresi yok"})

    results = []
    with open(DATA_FILE, "r", errors="ignore") as f:
        for line in f:
            if q in line:
                results.append(line.strip())
                if len(results) >= 50:
                    break

    return jsonify({
        "query": q,
        "count": len(results),
        "results": results
    })
