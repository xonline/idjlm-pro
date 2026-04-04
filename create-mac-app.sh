#!/bin/bash
# macOS app bundler for DJ Library Manager using PyInstaller.
# This script creates a standalone .app bundle with all dependencies.

set -e

echo "Building DJ Library Manager.app..."

cd "$(dirname "$0")"

# Verify Python 3.10+
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Using Python $PYTHON_VERSION"

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "Error: Python 3.10+ required"
    exit 1
fi

# Create venv if needed
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Install dependencies
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet pyinstaller pywebview

# Build app
pyinstaller \
    --name "DJ Library Manager" \
    --onedir \
    --windowed \
    --add-data "templates:templates" \
    --add-data "app/static:app/static" \
    --add-data "taxonomy.json:." \
    --add-data "config.example.env:." \
    --collect-all flask \
    --collect-all flask_cors \
    --collect-all mutagen \
    --collect-all librosa \
    --collect-all google.generativeai \
    --collect-all spotipy \
    --collect-all watchdog \
    --hidden-import webview \
    run_app.py

echo ""
echo "✅ App created: dist/DJ Library Manager.app"
echo ""
echo "To run:"
echo "  open dist/DJ\ Library\ Manager.app"
echo ""
echo "To share:"
echo "  zip -r 'DJ Library Manager.zip' 'dist/DJ Library Manager.app'"
echo ""
