import telebot
import os
import zipfile
import py7zr
import re
import shutil
from flask import Flask, request, jsonify, send_file

# ================= AYARLAR =================
TOKEN = os.environ.get("BOT_TOKEN", "BOT_TOKEN_BURAYA")
BASE_URL = os.environ.get("BASE_URL", "https://lordv3api.onrender.com")

MAX_UPLOAD_MB = 50 
MAX_JSON_RESULT = 5 # Kaç satırdan sonra TXT dosyası versin?

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Klasör Yapısı
STORAGE = "storage"      # Aktif API dosyaları
DISABLED = "disabled"    # Devre dışı bırakılanlar
UPLOAD_DIR = "uploads"
TEMP_DIR = "temp_extract"
OUT_DIR = "out"

for d in (STORAGE, DISABLED, UPLOAD_DIR, TEMP_DIR, OUT_DIR):
    os.makedirs(d, exist_ok=True)

# ================= YARDIMCI FONKSİYONLAR =================
def clean_name(text):
    return re.sub(r'[^a-zA-Z0-9_]', '', text).lower()

def add_lines_to_storage(lines, dataset_name):
    data_path = os.path.join(STORAGE, f"{dataset_name}.txt")
    with open(data_path, "a", encoding="utf-8", errors="ignore") as out:
        for line in lines:
            if line.strip():
                out.write(line.strip() + "\n")

# ================= TELEGRAM BOT KOMUTLARI =================

@bot.message_handler(commands=["start"])
def start(m):
    msg = (
        "🚀 **LORD API YÖNETİM PANELİ**\n\n"
        "📂 **Veri Yükleme:** Sadece TXT, ZIP veya 7Z gönder.\n"
        "📜 /listele - Tüm aktif API'leri gör\n"
        "🔴 /sil [isim] - API'yi kalıcı olarak siler\n"
        "⚪ /kapat [isim] - API'yi geçici olarak durdurur\n"
        "🟢 /ac [isim] - Kapatılan API'yi geri açar\n\n"
        f"⚠️ Limit: {MAX_UPLOAD_MB} MB"
    )
    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=["listele"])
def list_apis(m):
    files = [f.replace(".txt", "") for f in os.listdir(STORAGE) if f.endswith(".txt")]
    dis = [f.replace(".txt", "") for f in os.listdir(DISABLED) if f.endswith(".txt")]
    
    text = "📂 **AKTİF APİLER:**\n" + ("\n".join([f"✅ {x}" for x in files]) if files else "Boş")
    text += "\n\n🚫 **KAPALI APİLER:**\n" + ("\n".join([f"❌ {x}" for x in dis]) if dis else "Boş")
    
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["sil"])
def delete_api(m):
    name = clean_name(m.text.replace("/sil", "").strip())
    path = os.path.join(STORAGE, f"{name}.txt")
    if os.path.exists(path):
        os.remove(path)
        bot.reply_to(m, f"🗑️ `{name}` API'si ve dosyası tamamen silindi.")
    else:
        bot.reply_to(m, "❌ Dosya bulunamadı.")

@bot.message_handler(commands=["kapat"])
def disable_api(m):
    name = clean_name(m.text.replace("/kapat", "").strip())
    src = os.path.join(STORAGE, f"{name}.txt")
    dst = os.path.join(DISABLED, f"{name}.txt")
    if os.path.exists(src):
        shutil.move(src, dst)
        bot.reply_to(m, f"🔴 `{name}` API'si erişime kapatıldı.")
    else:
        bot.reply_to(m, "❌ Aktif API bulunamadı.")

@bot.message_handler(commands=["ac"])
def enable_api(m):
    name = clean_name(m.text.replace("/ac", "").strip())
    src = os.path.join(DISABLED, f"{name}.txt")
    dst = os.path.join(STORAGE, f"{name}.txt")
    if os.path.exists(src):
        shutil.move(src, dst)
        bot.reply_to(m, f"🟢 `{name}` API'si tekrar aktif!")
    else:
        bot.reply_to(m, "❌ Kapalılar listesinde bulunamadı.")

@bot.message_handler(content_types=["document"])
def handle_docs(m):
    try:
        if m.document.file_size / (1024*1024) > MAX_UPLOAD_MB:
            return bot.reply_to(m, "❌ 50 MB sınırı aşıldı.")

        file_info = bot.get_file(m.document.file_id)
        raw = bot.download_file(file_info.file_path)
        fname = m.document.file_name
        d_name = clean_name(os.path.splitext(fname)[0])
        t_path = os.path.join(UPLOAD_DIR, fname)

        with open(t_path, "wb") as f: f.write(raw)

        # İşleme
        if fname.lower().endswith((".txt", ".json")):
            with open(t_path, "r", encoding="utf-8", errors="ignore") as f:
                add_lines_to_storage(f.readlines(), d_name)
        elif fname.lower().endswith(".zip"):
            with zipfile.ZipFile(t_path) as z:
                for n in z.namelist():
                    if n.lower().endswith(".txt"):
                        add_lines_to_storage(z.read(n).decode(errors="ignore").splitlines(), d_name)
        elif fname.lower().endswith(".7z"):
            with py7zr.SevenZipFile(t_path, 'r') as z:
                z.extractall(TEMP_DIR)
                for root, _, files in os.walk(TEMP_DIR):
                    for f in files:
                        if f.lower().endswith(".txt"):
                            with open(os.path.join(root, f), "r", errors="ignore") as file:
                                add_lines_to_storage(file.readlines(), d_name)
            shutil.rmtree(TEMP_DIR)
            os.makedirs(TEMP_DIR, exist_ok=True)

        os.remove(t_path)
        bot.reply_to(m, f"✅ `{d_name}` yüklendi.\nURL: `{BASE_URL}/api/v1/search/{d_name}?q=SORGUN`", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Hata: {e}")

# ================= API MOTORU =================

@app.route("/api/v1/search/<dataset>")
def search(dataset):
    ds = clean_name(dataset)
    q = request.args.get("q", "").strip()
    
    if not q: return jsonify({"error": "Sorgu (q) girmediniz"}), 400
    
    path = os.path.join(STORAGE, f"{ds}.txt")
    if not os.path.exists(path):
        return jsonify({"error": "API devre dışı veya mevcut değil"}), 404

    results = []
    # Dosyayı satır satır tarar, sadece eşleşenleri alır
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if q.lower() in line.lower():
                results.append(line.strip())

    if not results:
        return jsonify({"status": "empty", "results": []})

    # Sonuç yönetimi
    if len(results) <= MAX_JSON_RESULT:
        return jsonify({
            "status": "success",
            "count": len(results),
            "results": results
        })
    else:
        out_path = os.path.join(OUT_DIR, f"{ds}_result.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(results))
        return send_file(out_path, as_attachment=True)

@app.route("/")
def index(): return "LORD API SYSTEM ACTIVE"

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"{BASE_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
