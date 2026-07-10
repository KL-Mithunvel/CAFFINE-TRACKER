#!/usr/bin/env bash
# One-time setup + run for Linux/macOS dev machines.
# Creates the venv if missing, installs dependencies, then starts the app.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "Starting Caffeine Tracker..."
python main.py
