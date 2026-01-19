import telebot
import os
import zipfile
import py7zr
from flask import Flask, request, jsonify

TOKEN = "8467419515:AAHfTf2QndCl7IoV0-VNVo-p7GvDM7_3N9E"
BASE_URL = "https://lordv3api.onrender.com"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

STORAGE = "storage"
UPLOAD_DIR = "uploads"
TEMP_DIR = "temp"

os.makedirs(STORAGE, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ================= WEBHOOK =================
bot.remove_webhook()
bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = telebot.types.Update.de_json(
        request.stream.read().decode("utf-8")
    )
    bot.process_new_updates([update])
    return "OK", 200

# ================= BOT =================
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "✅ LORD API FREE\n\n"
        "📂 TXT / ZIP / 7Z / JSON gönder\n"
        "📌 Her dosya için özel API oluşturulur"
    )

@bot.message_handler(content_types=["document"])
def handle_file(m):
    try:
        file_info = bot.get_file(m.document.file_id)
        raw = bot.download_file(file_info.file_path)

        filename = m.document.file_name
        name = os.path.splitext(filename)[0]

        data_path = os.path.join(STORAGE, f"{name}.txt")

        added = 0

        def add_lines(lines):
            nonlocal added
            with open(data_path, "a", errors="ignore") as out:
                for l in lines:
                    l = l.strip()
                    if l:
                        out.write(l + "\n")
                        added += 1

        temp_file = os.path.join(UPLOAD_DIR, filename)
        with open(temp_file, "wb") as f:
            f.write(raw)

        if filename.endswith((".txt", ".json")):
            with open(temp_file, "r", errors="ignore") as f:
                add_lines(f.readlines())

        elif filename.endswith(".zip"):
            with zipfile.ZipFile(temp_file) as z:
                for n in z.namelist():
                    if n.endswith(".txt"):
                        with z.open(n) as f:
                            add_lines(
                                f.read().decode(errors="ignore").splitlines()
                            )

        elif filename.endswith(".7z"):
            with py7zr.SevenZipFile(temp_file, "r") as z:
                z.extractall(TEMP_DIR)
            for root, _, files in os.walk(TEMP_DIR):
                for file in files:
                    if file.endswith(".txt"):
                        with open(os.path.join(root, file), "r", errors="ignore") as f:
                            add_lines(f.readlines())

        api_link = f"{BASE_URL}/api/v1/search/{name}?ara=DEGER"

        bot.send_message(
            m.chat.id,
            f"✅ Dosya işlendi\n"
            f"📦 Dosya: {filename}\n"
            f"📄 Eklenen satır: {added}\n\n"
            f"🌐 Özel API:\n{api_link}"
        )

    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Hata: {e}")

# ================= API =================
@app.route("/")
def home():
    return "LORD SYSTEM SORGU V3"

@app.route("/api/v1/search/<dataset>")
def search(dataset):
    q = request.args.get("ara", "").strip()
    path = os.path.join(STORAGE, f"{dataset}.txt")

    if not os.path.exists(path):
        return jsonify({"error": "dataset bulunamadı"})

    results = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if q in line:
                results.append(line.strip())
                if len(results) >= 50:
                    break

    return jsonify({
        "dataset": dataset,
        "query": q,
        "count": len(results),
        "results": results
    })
