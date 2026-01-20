import telebot
import os, re, zipfile, py7zr, uuid
from flask import Flask, request, jsonify, send_file

# ================= AYARLAR =================
TOKEN = "8467419515:AAF1gfziyraoZOX_t7gs2kPS_qyfwif-bV0"
BASE_URL = "https://lordv3api.onrender.com"

MAX_UPLOAD_MB = 30
MAX_JSON_RESULTS = 3   # 🔥 JSON EN FAZLA 3

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

STORAGE = "storage"
UPLOAD_DIR = "uploads"
TEMP_DIR = "temp"

for d in (STORAGE, UPLOAD_DIR, TEMP_DIR):
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
        "📂 TXT / ZIP / 7Z / JSON\n"
        "📦 Maksimum dosya: 30 MB\n"
        "🔎 TC / AD / GSM / SIRA NO\n"
        "📄 JSON max 3 kayıt"
    )

@bot.message_handler(content_types=["document"])
def handle_file(m):
    try:
        if m.document.file_size > MAX_UPLOAD_MB * 1024 * 1024:
            bot.send_message(m.chat.id, "❌ Dosya 30 MB sınırını aşıyor")
            return

        file_info = bot.get_file(m.document.file_id)
        raw = bot.download_file(file_info.file_path)
        filename = m.document.file_name

        dataset = re.sub(r'[^a-zA-Z0-9_]', '',
                          os.path.splitext(filename)[0]).lower()
        data_path = os.path.join(STORAGE, f"{dataset}.txt")

        temp_file = os.path.join(UPLOAD_DIR, filename)
        with open(temp_file, "wb") as f:
            f.write(raw)

        added = 0

        def add_lines(lines):
            nonlocal added
            with open(data_path, "a", encoding="utf-8", errors="ignore") as out:
                for l in lines:
                    l = l.strip()
                    if l:
                        out.write(l + "\n")
                        added += 1

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
            f"✅ Dataset hazır\n"
            f"📦 {dataset}\n"
            f"📄 Satır: {added}\n\n"
            f"🔗 {BASE_URL}/api/v1/search/{dataset}?ara=DEGER"
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
    q = request.args.get("ara", "").strip()

    path = os.path.join(STORAGE, f"{dataset}.txt")
    if not os.path.exists(path):
        return jsonify({"error": "dataset bulunamadı"})

    results = []
    temp_txt = None

    with open(path, "r", errors="ignore") as f:
        for line in f:
            if not q or q in line:
                results.append(line.strip())

                # 🔥 3'ü geçerse TXT'ye geç
                if len(results) > MAX_JSON_RESULTS:
                    temp_name = f"result_{uuid.uuid4().hex}.txt"
                    temp_txt = os.path.join(TEMP_DIR, temp_name)

                    with open(temp_txt, "w", encoding="utf-8") as out:
                        for r in results:
                            out.write(r + "\n")
                        for l in f:
                            if not q or q in l:
                                out.write(l)

                    break

    if temp_txt:
        return send_file(
            temp_txt,
            as_attachment=True,
            download_name="sonuc.txt",
            mimetype="text/plain"
        )

    return jsonify({
        "dataset": dataset,
        "query": q,
        "count": len(results),
        "results": results
    })
