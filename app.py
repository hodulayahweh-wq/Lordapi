from flask import Flask, request, jsonify, send_file
import os, tempfile, zipfile, json
from py7zr import SevenZipFile

app = Flask(__name__)

DATA_DIR = "storage"
MERGED_FILE = os.path.join(DATA_DIR, "data.txt")
TEMP_DIR = "temp"

API_KEYS = {
    "lord123": "VIP"
}

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def check_key(req):
    return req.args.get("apikey") in API_KEYS

@app.route("/")
def home():
    return "<h1>LORD SYSTEM SORGU V3</h1>"

@app.route("/api/v1/search")
def search():
    if not check_key(request):
        return jsonify({"error": "API KEY YOK"}), 401

    q = request.args.get("ara")
    if not q:
        return jsonify({"error": "ara parametresi yok"}), 400

    if not os.path.exists(MERGED_FILE):
        return jsonify({"error": "veri yok"}), 404

    results = []
    MAX_JSON = 50

    with open(MERGED_FILE, "r", errors="ignore") as f:
        for line in f:
            if q.lower() in line.lower():
                results.append(line.strip())
                if len(results) > MAX_JSON:
                    break

    if not results:
        return jsonify({"result": "YOK"})

    if len(results) <= MAX_JSON:
        return jsonify({"count": len(results), "data": results})

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    with open(MERGED_FILE, "r", errors="ignore") as f:
        for line in f:
            if q.lower() in line.lower():
                tmp.write(line.encode("utf-8", errors="ignore"))
    tmp.close()

    return send_file(tmp.name, as_attachment=True, download_name="sonuclar.txt")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
