#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Create venv if needed
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install/upgrade deps
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Legacy cloud-enrichment settings remain optional. The local Library,
# review, write and export workflow starts without any provider credential.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

PORT="${FLASK_PORT:-5050}"

echo ""
echo "  IDJLM Pro"
echo "  Open: http://localhost:$PORT"
echo ""

python3 run_app.py
