@echo off
cd /d "%~dp0"

echo ==========================================
echo YouTube Local Downloader - Setup
echo ==========================================
echo.

where py >nul 2>&1
if errorlevel 1 (
    echo Python was not found.
    echo Install Python 3.10+ from python.org and make sure Python is in PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment.
        pause
        exit /b 1
    )
)

echo.
echo Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo.
echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo ==========================================
echo Setup complete.
echo Run start.bat to start the application.
echo ==========================================
pause
