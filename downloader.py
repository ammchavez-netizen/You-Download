"""
YouTube downloader backend.

Usage:
    python downloader.py "https://www.youtube.com/watch?v=..." "downloads"

This example uses yt-dlp. Only download content you have permission
to download and use.
"""

import sys
import os
from pathlib import Path
    
try:
    import yt_dlp
except ImportError:
    print("yt-dlp is not installed. Run: python -m pip install -U yt-dlp", file=sys.stderr)
    sys.exit(1)


def download_video(url: str, output_dir: str) -> None:
    output_path = Path(output_dir)
    #output_path.mkdir(parents=True, exist_ok=True)


    class SilentLogger:
        def debug(self, msg): pass
        def info(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): print(msg, file=sys.stderr)
            
    options = {
        "format": "bv*+ba/b",
        "outtmpl": str(output_path / "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "windowsfilenames": True,

        # Use Deno for YouTube JavaScript challenges.
        "js_runtimes": {
            "deno": {}
        },

        "quiet": True,
        "no_warnings": True,
        "logger": SilentLogger(),
    }

    print(f"Starting download...\n{url}")

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    print(f"\nDownload completed!\nFile is saved in: {output_path.resolve()}")
    os.startfile(output_path)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <youtube_url> [output_directory]", file=sys.stderr)
        sys.exit(2)

    video_url = sys.argv[1]
    #output_directory = sys.argv[2] if len(sys.argv) >= 3 else "downloads"
    output_directory = Path.home() / "Downloads"
    try:
        download_video(video_url, output_directory)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)
