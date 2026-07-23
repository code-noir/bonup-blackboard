#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/../frontend"

echo "Starting Vite frontend on http://0.0.0.0:5173 ..."
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort
