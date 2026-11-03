"""
YouTube downloader backend.

Usage:
    python downloader.py "https://www.youtube.com/watch?v=..." [output_directory] [mp4|mp3]

Progress is written to stdout as one JSON object per line so app.py can
relay it to the browser while the download is running:

    {"type": "status",   "title": "...", "format": "MP4", "message": "..."}
    {"type": "progress", "title": "...", "format": "MP4", "percent": 42.0, ...}
    {"type": "done",     "title": "...", "format": "MP4", "message": "..."}

This example uses yt-dlp. Only download content you have permission
to download and use.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("yt-dlp is not installed. Run: python -m pip install -U yt-dlp", file=sys.stderr)
    sys.exit(1)


FORMATS = ("mp4", "mp3")


def emit(**event) -> None:
    """Write one progress event as a JSON line and flush it immediately."""
    print(json.dumps(event, ensure_ascii=False), flush=True)


def format_bytes(num) -> str:
    if not num:
        return ""
    for unit in ("B", "KiB", "MiB", "GiB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TiB"


def format_eta(seconds) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def build_options(work_path: Path, fmt: str) -> dict:
    class SilentLogger:
        def debug(self, msg): pass
        def info(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): print(msg, file=sys.stderr, flush=True)

    options = {
        "outtmpl": str(work_path / "%(title)s.%(ext)s"),
        "noplaylist": True,
        "windowsfilenames": True,

        # Use Deno for YouTube JavaScript challenges.
        "js_runtimes": {
            "deno": {}
        },

        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": SilentLogger(),
    }

    if fmt == "mp3":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        options.update({
            # Prefer H.264 video + AAC audio. YouTube's "best" streams are often
            # AV1 or VP9, which play in most media players but show a black
            # screen in vMix and other broadcast/editing software.
            "format": (
                "bv*[vcodec^=avc1]+ba[acodec^=mp4a]"
                "/bv*[vcodec^=avc1]+ba"
                "/b[vcodec^=avc1]"
                "/bv*+ba/b"
            ),
            "merge_output_format": "mp4",
        })

    return options


def probe_codecs(path: Path) -> tuple:
    """Return (video_codec, audio_codec, pixel_format) using ffprobe."""
    def probe(stream, entries):
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", f"stream={entries}", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    video = probe("v:0", "codec_name,pix_fmt")
    audio = probe("a:0", "codec_name")
    return (video[0] if video else None,
            audio[0] if audio else None,
            video[1] if len(video) > 1 else None)


def ensure_compatible_mp4(path: Path, title: str, label: str, duration) -> None:
    """Re-encode to H.264 (8-bit) + AAC if the download isn't already, so the
    MP4 works in vMix. Only runs when YouTube had no H.264 version."""
    vcodec, acodec, pix_fmt = probe_codecs(path)
    video_ok = vcodec in (None, "h264") and pix_fmt in (None, "yuv420p", "yuvj420p")
    audio_ok = acodec in (None, "aac")
    if video_ok and audio_ok:
        return

    emit(type="status", title=title, format=label,
         message="Converting to H.264/AAC for vMix compatibility (this can take a while)...")

    temp_out = path.with_name(path.stem + ".h264-tmp.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(path)]
    cmd += (["-c:v", "copy"] if video_ok else
            ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"])
    cmd += (["-c:a", "copy"] if audio_ok else ["-c:a", "aac", "-b:a", "192k"])
    cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(temp_out)]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, errors="replace")
    last = -1
    for line in proc.stdout:
        key, _, value = line.strip().partition("=")
        if key == "out_time_us" and duration and value.isdigit():
            percent = min(round(int(value) / 1e6 * 100 / duration, 1), 100.0)
            if int(percent) != last:
                last = int(percent)
                emit(type="progress", title=title, format=label, stream="converting",
                     percent=percent, downloaded="", total="", speed="", eta="")
    stderr = proc.stderr.read()
    if proc.wait() != 0:
        temp_out.unlink(missing_ok=True)
        raise RuntimeError(f"Could not convert to H.264: {stderr.strip()[-300:]}")

    os.replace(temp_out, path)
    emit(type="status", title=title, format=label, message="Conversion finished.")


def download_video(url: str, output_dir, fmt: str = "mp4") -> None:
    fmt = fmt.lower()
    label = fmt.upper()
    output_path = Path(output_dir)
    #output_path.mkdir(parents=True, exist_ok=True)

    state = {"title": None, "last_emit": 0.0, "last_percent": -1}

    def progress_hook(d):
        title = state["title"]
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            percent = round(done * 100 / total, 1) if total else None

            # Throttle: at most ~4 updates per second unless the percent jumps.
            now = time.monotonic()
            whole = int(percent) if percent is not None else -1
            if now - state["last_emit"] < 0.25 and whole == state["last_percent"]:
                return
            state["last_emit"] = now
            state["last_percent"] = whole

            # For MP4, video and audio arrive as separate streams before merging.
            info = d.get("info_dict") or {}
            stream = ""
            if fmt == "mp4" and info.get("requested_formats") is None:
                if info.get("vcodec") == "none":
                    stream = "audio"
                elif info.get("acodec") == "none":
                    stream = "video"

            emit(
                type="progress",
                title=title,
                format=label,
                stream=stream,
                percent=percent,
                downloaded=format_bytes(done),
                total=format_bytes(total),
                speed=format_bytes(d.get("speed")) + "/s" if d.get("speed") else "",
                eta=format_eta(d.get("eta")),
            )
        elif d["status"] == "finished":
            state["last_percent"] = -1
            emit(type="progress", title=title, format=label, stream="", percent=100.0,
                 downloaded="", total="", speed="", eta="")

    def postprocessor_hook(d):
        if d["status"] != "started":
            return
        name = d.get("postprocessor", "")
        if name == "Merger":
            message = f"Merging video and audio into {label}..."
        elif name == "ExtractAudio":
            message = f"Converting to {label}..."
        else:
            return
        if message != state.get("last_status"):
            state["last_status"] = message
            emit(type="status", title=state["title"], format=label, message=message)

    # MP3s are downloaded and converted in a temporary folder, then only the
    # finished .mp3 is moved to the output folder. Otherwise the conversion
    # step could delete an existing MP4 of the same video in Downloads.
    temp_dir = Path(tempfile.mkdtemp(prefix="you-download-")) if fmt == "mp3" else None
    try:
        _run(url, output_path, fmt, label, state, temp_dir,
             progress_hook, postprocessor_hook)
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    if hasattr(os, "startfile"):  # Windows only
        os.startfile(output_path)


def _run(url, output_path, fmt, label, state, temp_dir, progress_hook, postprocessor_hook):
    options = build_options(temp_dir or output_path, fmt)
    options["progress_hooks"] = [progress_hook]
    options["postprocessor_hooks"] = [postprocessor_hook]

    with yt_dlp.YoutubeDL(options) as ydl:
        emit(type="status", title=None, format=label, message="Fetching video information...")

        # Look up the video first so progress can show its real title.
        info = ydl.extract_info(url, download=False)
        state["title"] = info.get("title") or url
        emit(type="status", title=state["title"], format=label,
             message=f"Downloading \"{state['title']}\" as {label}...")

        # Reuse the extracted info instead of fetching the page a second time.
        info = ydl.process_ie_result(info, download=True)

    downloads = info.get("requested_downloads") or []
    filepath = downloads[0].get("filepath") if downloads else None
    filename = Path(filepath).name if filepath else f"{state['title']}.{fmt}"

    if fmt == "mp4" and filepath and Path(filepath).exists():
        ensure_compatible_mp4(Path(filepath), state["title"], label, info.get("duration"))

    if temp_dir and filepath:
        destination = output_path / filename
        if destination.exists():
            destination.unlink()  # replace an older MP3 of the same video
        shutil.move(filepath, destination)

    emit(
        type="done",
        title=state["title"],
        format=label,
        filename=filename,
        message=f"Download completed!\n{filename}\nFile is saved in: {output_path.resolve()}",
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <youtube_url> [output_directory] [mp4|mp3]", file=sys.stderr)
        sys.exit(2)

    video_url = sys.argv[1]
    #output_directory = sys.argv[2] if len(sys.argv) >= 3 else "downloads"
    output_directory = Path.home() / "Downloads"
    output_format = sys.argv[3].lower() if len(sys.argv) >= 4 else "mp4"

    if output_format not in FORMATS:
        print(f"Unsupported format: {output_format}. Use mp4 or mp3.", file=sys.stderr)
        sys.exit(2)

    try:
        download_video(video_url, output_directory, output_format)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)
