#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Create .env from example if it doesn't exist
if [ ! -f .env ]; then
  cp config.example.env .env
  echo "Created .env from config.example.env — add your GEMINI_API_KEY to .env before running."
  exit 1
fi

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

# Load env vars
export $(grep -v '^#' .env | grep -v '^$' | xargs)

PORT="${FLASK_PORT:-5050}"

echo ""
echo "  IDLM Pro"
echo "  Open: http://localhost:$PORT"
echo ""

python3 -m flask --app app run --port "$PORT"
