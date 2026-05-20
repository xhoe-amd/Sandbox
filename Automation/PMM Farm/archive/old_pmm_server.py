from flask import Flask, jsonify
import os
from queue import Queue
import threading

app = Flask(__name__)

# =========================
# CONFIG
# =========================
FILES_DIR = "output/2026-W21"  # your permutation folder

file_queue = Queue()
lock = threading.Lock()

# =========================
# Load files into queue
# =========================
def load_files():
    for f in os.listdir(FILES_DIR):
        file_queue.put(f)

    print(f"✅ Loaded {file_queue.qsize()} files into queue")


# =========================
# API: Get next file
# =========================
@app.route("/get_job", methods=["GET"])
def get_job():
    with lock:
        if file_queue.empty():
            return jsonify({"status": "empty"})

        file_name = file_queue.get()

    return jsonify({
        "status": "ok",
        "file": file_name
    })


# =========================
# API: Download file content
# =========================
@app.route("/get_file/<filename>", methods=["GET"])
def get_file(filename):
    file_path = os.path.join(FILES_DIR, filename)

    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "file not found"})

    with open(file_path, "r") as f:
        content = f.read()

    return jsonify({
        "status": "ok",
        "content": content
    })


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    load_files()
    app.run(host="0.0.0.0", port=5000)