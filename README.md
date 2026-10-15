# YouTube Video Downloader

A simple Windows 11 local web application using:

- HTML
- CSS
- JavaScript
- Python Flask
- yt-dlp

## 1. Requirements

Install Python 3.10 or newer.
	
	winget install Python.Python.3.12

During Python installation, enable:

    Add python.exe to PATH

Install the FFmpeg package.

	winget install Gyan.FFmpeg.Shared

Install the JS runtime Deno

	winget install DenoLand.Deno

## 2. Setup

Double-click:

    setup.bat

This creates `.venv` and installs Flask and yt-dlp.

## 3. Start

Double-click:

    start.bat

Optional:

    - Create a shortcut of start.bat on desktop.

    - Change the icon using image-_7_.ico.

    - Rename the start.bat shortcut.

## 4. Download

Paste a YouTube URL into the webpage, choose a format, and click Download.

- **MP4** (default): video with audio
- **MP3**: audio only (converted with FFmpeg)

While downloading, the page shows the video's title, the chosen format,
and a progress bar with percentage, size, speed and time remaining.

Downloaded files are saved in:

    /Downloads

## How it works

Browser -> Flask -> downloader.py -> yt-dlp -> /Downloads

Flask starts each download as a background job. `downloader.py` prints
progress as JSON lines, and the page polls `/progress/<job_id>` to show it.

The URL is passed to Python as an argument rather than being placed
directly into a shell command.

## Legal / platform note

Download only content that you have permission to download and use.
Respect YouTube's terms and applicable copyright law.

## Customizing downloader.py

The Flask application does not need to change if you modify the
yt-dlp options in `downloader.py`.

For example, you can later add:

- selectable video quality
- MP4/MKV output
- playlist support
- custom download folders


