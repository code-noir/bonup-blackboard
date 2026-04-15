#!/usr/bin/env bash
# Starts backend and frontend in the background.
# Logs go to dev/logs/backend.log and dev/logs/frontend.log.
# Run `./dev/stop-all.sh` to kill both processes.

set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="$REPO/dev/logs"
mkdir -p "$LOGS"

echo "Starting backend..."
bash "$REPO/dev/start-backend.sh" >"$LOGS/backend.log" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend..."
bash "$REPO/dev/start-frontend.sh" >"$LOGS/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo "$BACKEND_PID" >"$LOGS/backend.pid"
echo "$FRONTEND_PID" >"$LOGS/frontend.pid"

echo ""
echo "Both services started."
echo "  Backend PID : $BACKEND_PID  (log: dev/logs/backend.log)"
echo "  Frontend PID: $FRONTEND_PID (log: dev/logs/frontend.log)"
echo ""
echo "URLs:"
echo "  Backend  -> http://localhost:8000"
echo "  Frontend -> http://localhost:5173"
echo ""
echo "To stop: ./dev/stop-all.sh"
echo "To tail logs: tail -f dev/logs/backend.log dev/logs/frontend.log"
