from flask import Flask, render_template, request, jsonify
from pathlib import Path
import json
import os
import subprocess
import sys
import re
import threading
import time
import uuid

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
#DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR = Path.home() / "Downloads"
#DOWNLOAD_DIR.mkdir(exist_ok=True)

DOWNLOAD_TIMEOUT = 3600  # seconds
FORMATS = ("mp4", "mp3")

YOUTUBE_RE = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+)([&?][^\s]*)?$",
    re.IGNORECASE
)

# In-memory job registry: job_id -> state dict. Fine for a single local user.
jobs = {}
jobs_lock = threading.Lock()


def update_job(job_id, **fields):
    with jobs_lock:
        jobs[job_id].update(fields)


def prune_old_jobs():
    cutoff = time.time() - 3600
    with jobs_lock:
        for job_id in [j for j, s in jobs.items() if s["finished"] and s["created"] < cutoff]:
            del jobs[job_id]


def run_download(job_id, url, fmt):
    """Run downloader.py in a subprocess and record its JSON progress lines."""
    # Force UTF-8 so video titles with non-English characters survive the pipe on Windows.
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    log_lines = []

    try:
        # Calls downloader.py using the same Python interpreter running Flask.
        # The URL is passed as a separate argument, not concatenated into a shell command.
        proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "downloader.py"), url, str(DOWNLOAD_DIR), fmt],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except Exception as exc:
        update_job(job_id, finished=True, success=False, message=f"Server error: {exc}")
        return

    timed_out = threading.Event()

    def kill_on_timeout():
        timed_out.set()
        proc.kill()

    timer = threading.Timer(DOWNLOAD_TIMEOUT, kill_on_timeout)
    timer.start()

    try:
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                log_lines.append(line)  # error text or other plain output
                continue
            if not isinstance(event, dict):
                log_lines.append(line)
                continue

            fields = {k: event[k] for k in ("title", "format") if event.get(k)}
            if event.get("type") == "progress":
                fields["progress"] = event
            elif event.get("type") == "status":
                fields["message"] = event.get("message", "")
                fields["progress"] = None
            elif event.get("type") == "done":
                fields["message"] = event.get("message", "")
                fields["done_event"] = True
                fields["progress"] = None
            update_job(job_id, **fields)

        proc.wait()
    finally:
        timer.cancel()

    if timed_out.is_set():
        update_job(job_id, finished=True, success=False,
                   message="The download exceeded the 60-minute limit.")
    elif proc.returncode != 0:
        failed = [l for l in log_lines if l.startswith("Download failed:")]
        update_job(job_id, finished=True, success=False,
                   message=(failed[-1] if failed else "\n".join(log_lines[-5:]))
                   or "The downloader returned an error.")
    else:
        with jobs_lock:
            job = jobs[job_id]
            if not job.get("done_event"):
                job["message"] = "Download completed successfully."
            job.update(finished=True, success=True, progress=None)


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    fmt = (data.get("format") or "mp4").strip().lower()

    if not url:
        return jsonify({"success": False, "message": "Please enter a YouTube URL."}), 400

    if fmt not in FORMATS:
        return jsonify({"success": False, "message": "Please choose MP4 or MP3."}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not YOUTUBE_RE.match(url):
        return jsonify({"success": False, "message": "Please enter a valid YouTube URL."}), 400

    prune_old_jobs()
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "created": time.time(),
            "format": fmt.upper(),
            "title": None,
            "message": "Starting download...",
            "progress": None,
            "finished": False,
            "success": None,
        }

    threading.Thread(target=run_download, args=(job_id, url, fmt), daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})


@app.get("/progress/<job_id>")
def progress(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return jsonify({"success": False, "message": "Unknown download."}), 404
        payload = {k: job.get(k) for k in ("format", "title", "message", "progress", "finished", "success")}
    payload["folder"] = str(DOWNLOAD_DIR)
    return jsonify(payload)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
