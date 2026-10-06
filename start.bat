@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run setup.bat first.
    pause
    exit /b 1
)

echo Starting YouTube Downloader...
echo.
echo Opening http://127.0.0.1:5000
echo.
echo Press CTRL+C in this window to stop the server.
echo.

start "" http://127.0.0.1:5000

".venv\Scripts\python.exe" app.py

pause