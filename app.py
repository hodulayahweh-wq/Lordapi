import telebot
import os
import zipfile
import py7zr
import re
from flask import Flask, request, jsonify, send_file

# ================= AYARLAR =================
TOKEN = os.environ.get("BOT_TOKEN", "BOT_TOKEN_BURAYA")
BASE_URL = os.environ.get("BASE_URL", "https://lordv3api.onrender.com")

MAX_UPLOAD_MB = 30
MAX_JSON_RESULT = 3

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

STORAGE = "storage"
UPLOAD_DIR = "uploads"
TEMP_DIR = "temp"
OUT_DIR = "out"

for d in (STORAGE, UPLOAD_DIR, TEMP_DIR, OUT_DIR):
    os.makedirs(d, exist_ok=True)

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
        "✅ LORD API\n\n"
        "📂 TXT / ZIP / 7Z / JSON gönder\n"
        "📦 Dosya limiti: 30 MB\n"
        "🔎 API gelen isteği otomatik okur\n"
        "📤 Fazla veri olursa TXT verir"
    )

@bot.message_handler(content_types=["document"])
def handle_file(m):
    try:
        size_mb = m.document.file_size / (1024 * 1024)
        if size_mb > MAX_UPLOAD_MB:
            bot.send_message(m.chat.id, "❌ Dosya 30 MB üstü")
            return

        file_info = bot.get_file(m.document.file_id)
        raw = bot.download_file(file_info.file_path)
        filename = m.document.file_name

        dataset = re.sub(r'[^a-zA-Z0-9_]', '', os.path.splitext(filename)[0]).lower()
        data_path = os.path.join(STORAGE, f"{dataset}.txt")

        def add_lines(lines):
            with open(data_path, "a", encoding="utf-8", errors="ignore") as out:
                for l in lines:
                    l = l.strip()
                    if l:
                        out.write(l + "\n")

        temp_file = os.path.join(UPLOAD_DIR, filename)
        with open(temp_file, "wb") as f:
            f.write(raw)

        if filename.lower().endswith((".txt", ".json")):
            with open(temp_file, "r", errors="ignore") as f:
                add_lines(f.readlines())

        elif filename.lower().endswith(".zip"):
            with zipfile.ZipFile(temp_file) as z:
                for n in z.namelist():
                    if n.lower().endswith(".txt"):
                        with z.open(n) as f:
                            add_lines(f.read().decode(errors="ignore").splitlines())

        elif filename.lower().endswith(".7z"):
            with py7zr.SevenZipFile(temp_file) as z:
                z.extractall(TEMP_DIR)
            for root, _, files in os.walk(TEMP_DIR):
                for file in files:
                    if file.lower().endswith(".txt"):
                        with open(os.path.join(root, file), "r", errors="ignore") as f:
                            add_lines(f.readlines())

        bot.send_message(
            m.chat.id,
            f"✅ Dataset yüklendi\n"
            f"📦 {dataset}\n\n"
            f"🔗 {BASE_URL}/api/v1/search/{dataset}?q=DEGER"
        )

    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Hata: {e}")

# ================= API =================
@app.route("/")
def home():
    return "LORD SYSTEM SORGU V3"

@app.route("/api/v1/search/<dataset>")
def search(dataset):
    dataset = re.sub(r'[^a-zA-Z0-9_]', '', dataset).lower()
    q = request.args.get("q", "").strip()

    path = os.path.join(STORAGE, f"{dataset}.txt")
    if not os.path.exists(path):
        return jsonify({"error": "dataset bulunamadı"})

    results = []
    with open(path, "r", errors="ignore") as f:
        for line in f:
            if q in line:
                results.append(line.strip())
                if len(results) > MAX_JSON_RESULT:
                    break

    # 🔹 JSON sınırı
    if len(results) <= MAX_JSON_RESULT:
        return jsonify({
            "dataset": dataset,
            "query": q,
            "count": len(results),
            "results": results
        })

    # 🔹 Fazlaysa TXT ver
    out_file = os.path.join(OUT_DIR, f"{dataset}_{q}.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        for r in results:
            f.write(r + "\n")

    return send_file(out_file, as_attachment=True)

# ================= RUN (ZORUNLU) =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
