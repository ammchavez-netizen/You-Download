@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found.
    echo Run setup.bat first.
    pause
    exit /b 1
)

echo Fetching updates from remote repo...
git fetch origin main >nul 2>&1

:: Check if the local main branch is behind the remote main branch
for /f "tokens=*" %%i in ('git rev-list --count main..origin/main') do set BEHIND=%%i

if "%BEHIND%"=="0" (
    echo Your app is up to date.
) else (
    echo Update found! Pulling the latest changes...
    git pull origin main >nul 2>&1
)

echo.

echo Starting YouTube Downloader...
echo.
echo Opening http://127.0.0.1:5000
echo.
echo To stop the server, press CTRL+C.
echo.

start "" http://127.0.0.1:5000

".venv\Scripts\python.exe" app.py

pause