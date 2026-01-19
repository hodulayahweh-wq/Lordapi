import telebot, os, zipfile, json
from py7zr import SevenZipFile

TOKEN = "8467419515:AAFIUi4154gL4QQfwmpjaLAE-ay12O6BjD8"
BASE_API = "https://lordv3api.onrender.com"

bot = telebot.TeleBot(TOKEN)

UPLOADS = "uploads"
DATA_FILE = "storage/data.txt"
TEMP = "temp"

os.makedirs(UPLOADS, exist_ok=True)
os.makedirs("storage", exist_ok=True)
os.makedirs(TEMP, exist_ok=True)

def write_text(path):
    if path.endswith(".txt"):
        with open(path, "r", errors="ignore") as f, open(DATA_FILE, "a", errors="ignore") as out:
            for line in f:
                out.write(line)

    elif path.endswith(".json"):
        with open(path, "r", errors="ignore") as f, open(DATA_FILE, "a", errors="ignore") as out:
            out.write(json.dumps(json.load(f), ensure_ascii=False) + "\n")

    elif path.endswith(".bin"):
        with open(path, "rb") as f, open(DATA_FILE, "a", errors="ignore") as out:
            out.write(f.read().decode(errors="ignore"))

    elif path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            z.extractall(TEMP)
        for r, _, fs in os.walk(TEMP):
            for fn in fs:
                write_text(os.path.join(r, fn))

    elif path.endswith(".7z"):
        with SevenZipFile(path) as z:
            z.extractall(path=TEMP)
        for r, _, fs in os.walk(TEMP):
            for fn in fs:
                write_text(os.path.join(r, fn))

@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id, "📤 Dosya gönder (.txt .zip .7z .json .bin)")

@bot.message_handler(content_types=["document"])
def handle(m):
    file = bot.get_file(m.document.file_id)
    data = bot.download_file(file.file_path)

    path = os.path.join(UPLOADS, m.document.file_name)
    with open(path, "wb") as f:
        f.write(data)

    write_text(path)

    bot.reply_to(
        m,
        "✅ Veri eklendi\n"
        f"🌐 API:\n{BASE_API}/api/v1/search?ara=ORNEK&apikey=lord123"
    )

bot.infinity_polling()
