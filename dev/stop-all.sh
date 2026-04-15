#!/usr/bin/env bash
LOGS="$(cd "$(dirname "$0")" && pwd)/logs"

stop_pid() {
    local label="$1"
    local pidfile="$LOGS/$2.pid"
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping $label (PID $PID)..."
            kill "$PID"
        else
            echo "$label (PID $PID) is not running."
        fi
        rm -f "$pidfile"
    else
        echo "No PID file for $label — may already be stopped."
    fi
}

stop_pid "backend"  "backend"
stop_pid "frontend" "frontend"

echo "Done."
