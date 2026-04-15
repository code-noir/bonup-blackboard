#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "Activating virtualenv..."
source venv/bin/activate

echo "Starting Django backend on http://0.0.0.0:8000 ..."
python manage.py runserver 0.0.0.0:8000
