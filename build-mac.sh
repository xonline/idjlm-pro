#!/bin/bash
# Builds a self-contained IDJLM Pro.app using PyInstaller.
# Run this once on your Mac. Output: dist/IDJLM Pro.app
# Share that .app (or zip it) — no Python/pip needed on the target machine.
#
# Requires Python 3.10+ (pywebview won't compile on 3.9).
# If Homebrew Python 3.12 is installed it will be used automatically.

set -e
cd "$(dirname "$0")"

echo ""
echo "  IDJLM Pro — Mac Build"
echo "  This will take a few minutes..."
echo ""

# Find Python 3.10+ — prefer newer Homebrew versions
PYTHON=""
for candidate in \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3.10 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.10 \
    python3.13 python3.12 python3.11 python3.10; do
    if command -v "$candidate" &>/dev/null 2>&1 || [ -x "$candidate" ]; then
        VER=$("$candidate" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || true)
        if [[ "$VER" == "(3, 1"* ]] || [[ "$VER" == "(3, 2"* ]]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "  ❌  Python 3.10+ not found."
    echo "  Install it with:  brew install python@3.12"
    echo ""
    exit 1
fi

echo "  Using Python: $PYTHON ($($PYTHON --version))"

# Create a fresh venv using the chosen Python
if [ ! -d .venv-build ]; then
    "$PYTHON" -m venv .venv-build
fi
source .venv-build/bin/activate

pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q pyinstaller

# Create .env if missing (bundled app needs it present)
if [ ! -f .env ]; then
    cp config.example.env .env
fi

# Build
pyinstaller \
    --noconfirm \
    --windowed \
    --name "IDJLM Pro" \
    --add-data "templates:templates" \
    --add-data "app/static:app/static" \
    --add-data "taxonomy.json:." \
    --add-data ".env:." \
    --hidden-import "engineio.async_drivers.threading" \
    --hidden-import "pkg_resources.py2_compat" \
    --hidden-import "webview.platforms.cocoa" \
    --hidden-import "webview.platforms.gtk" \
    --hidden-import "webview.platforms.qt" \
    --collect-all webview \
    --collect-all librosa \
    --collect-all mutagen \
    --collect-all flask \
    run_app.py

echo ""
echo "  ✅ Built: dist/IDJLM Pro.app"
echo ""
echo "  To distribute:"
echo "  zip -r 'IDJLM Pro.zip' 'dist/IDJLM Pro.app'"
echo ""
