#!/bin/bash
# Quick start script — sets up venv and runs the app locally.

set -e
cd "$(dirname "$0")"

echo "DJ Library Manager — Starting..."

# Create .env if missing
if [ ! -f .env ]; then
    cp config.example.env .env
    echo "Created .env from config.example.env"
fi

# Setup venv
if [ ! -d .venv ]; then
    python3 -m venv .venv
    echo "Created Python virtual environment"
fi
source .venv/bin/activate

# Install requirements
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Load env and start Flask
export $(cat .env | xargs)
python3 -m flask run --host=0.0.0.0 --port=${FLASK_PORT:-5050}
