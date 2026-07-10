@echo off
REM Caffeine Tracker launcher for Windows 11.
REM Creates the venv if missing, installs dependencies, then starts the app.
setlocal
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install --upgrade pip >nul
pip install -r requirements.txt

echo Starting Caffeine Tracker...
python main.py

pause
