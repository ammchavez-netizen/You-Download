from flask import Flask, render_template, request, jsonify
from pathlib import Path
import subprocess
import sys
import re

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
#DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR = Path.home() / "Downloads"
#DOWNLOAD_DIR.mkdir(exist_ok=True)

YOUTUBE_RE = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)([&?][^\s]*)?$",
    re.IGNORECASE
)

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"success": False, "message": "Please enter a YouTube URL."}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not YOUTUBE_RE.match(url):
        return jsonify({"success": False, "message": "Please enter a valid YouTube URL."}), 400

    try:
        # Calls downloader.py using the same Python interpreter running Flask.
        # The URL is passed as a separate argument, not concatenated into a shell command.
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "downloader.py"), url, str(DOWNLOAD_DIR)],
            capture_output=True,
            text=True,
            timeout=3600
        )

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()

        if result.returncode != 0:
            return jsonify({
                "success": False,
                "message": error or output or "The downloader returned an error."
            }), 500

        return jsonify({
            "success": True,
            "message": output or "Download completed successfully.",
            "folder": str(DOWNLOAD_DIR)
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "message": "The download exceeded the 60-minute limit."
        }), 500
    except Exception as exc:
        return jsonify({
            "success": False,
            "message": f"Server error: {exc}"
        }), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
