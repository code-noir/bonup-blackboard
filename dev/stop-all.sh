#!/usr/bin/env bash
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="$REPO/dev/logs"

stop_pid() {
    local label="$1"
    local pidfile="$LOGS/$2.pid"
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping $label (PID $PID)..."
            pkill -TERM -P "$PID" 2>/dev/null || true
            kill "$PID"
        else
            echo "$label (PID $PID) is not running."
        fi
        rm -f "$pidfile"
    else
        echo "No PID file for $label — may already be stopped."
    fi
}

stop_frontend_dev_servers() {
    local pattern="$REPO/frontend/node_modules/.bin/vite"
    if pgrep -f "$pattern" >/dev/null; then
        echo "Stopping frontend dev server processes..."
        pkill -TERM -f "$pattern" 2>/dev/null || true
        sleep 1
        if pgrep -f "$pattern" >/dev/null; then
            echo "Force stopping frontend dev server processes..."
            pkill -KILL -f "$pattern" 2>/dev/null || true
        fi
    fi
}

stop_pid "backend"  "backend"
stop_pid "frontend" "frontend"
stop_frontend_dev_servers

echo "Done."
