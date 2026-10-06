# YouTube Local Downloader

# New addition
You need to install the following using powershell:
winget install Gyan.FFmpeg.Shared
winget install DenoLand.Deno

A simple Windows 11 local web application using:

- HTML
- CSS
- JavaScript
- Python Flask
- yt-dlp

## 1. Requirements

Install Python 3.10 or newer.

During Python installation, enable:

    Add python.exe to PATH

## 2. Setup

Double-click:

    setup.bat

This creates `.venv` and installs Flask and yt-dlp.

## 3. Start

Double-click:

    start.bat

Then open:

    http://127.0.0.1:5000

## 4. Download

Paste a YouTube URL into the webpage and click Download.

Downloaded files are saved in:

    downloads\

## How it works

Browser -> Flask -> downloader.py -> yt-dlp -> downloads\

The URL is passed to Python as an argument rather than being placed
directly into a shell command.

## Legal / platform note

Download only content that you have permission to download and use.
Respect YouTube's terms and applicable copyright law.

## Customizing downloader.py

The Flask application does not need to change if you modify the
yt-dlp options in `downloader.py`.

For example, you can later add:

- audio-only downloads
- selectable video quality
- MP4/MKV output
- playlist support
- custom download folders
- progress reporting


