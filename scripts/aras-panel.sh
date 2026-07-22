#!/usr/bin/env bash
# Aras-GP Panel — background runner for Linux and macOS.
#
#   ./scripts/aras-panel.sh start     run detached; survives closing the terminal
#   ./scripts/aras-panel.sh stop      shut it down
#   ./scripts/aras-panel.sh restart
#   ./scripts/aras-panel.sh status
#   ./scripts/aras-panel.sh logs      follow the log
#
# Running `python -m panel` in a terminal ties the relay to that terminal: close
# it and the tunnel dies mid-session. This wraps the same process in nohup and
# tracks it with a PID file, without installing any system service.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/panel/data"
PID_FILE="$RUN_DIR/panel.pid"
LOG_FILE="$RUN_DIR/panel.log"

if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
else
    echo "پایتون پیدا نشد. اول venv بسازید:  python3 -m venv .venv" >&2
    exit 1
fi

mkdir -p "$RUN_DIR"
chmod 700 "$RUN_DIR" 2>/dev/null || true

running() {
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || echo)"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null
}

start() {
    if running; then
        echo "پنل از قبل در حال اجراست (PID $(cat "$PID_FILE"))."
        return 0
    fi
    cd "$ROOT"
    # setsid where available so the process leaves the terminal's session
    # entirely; nohup alone is enough on macOS.
    if command -v setsid >/dev/null 2>&1; then
        setsid nohup "$PY" -m panel >>"$LOG_FILE" 2>&1 < /dev/null &
    else
        nohup "$PY" -m panel >>"$LOG_FILE" 2>&1 < /dev/null &
    fi
    echo $! > "$PID_FILE"
    chmod 600 "$PID_FILE" 2>/dev/null || true

    sleep 2
    if running; then
        echo "پنل بالا آمد (PID $(cat "$PID_FILE"))  →  http://127.0.0.1:${ARAS_PANEL_PORT:-8600}"
        echo "لاگ: $LOG_FILE"
    else
        echo "بالا نیامد. آخرین خطوط لاگ:" >&2
        tail -20 "$LOG_FILE" >&2 || true
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop() {
    if ! running; then
        echo "پنل در حال اجرا نیست."
        rm -f "$PID_FILE"
        return 0
    fi
    local pid
    pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        running || break
        sleep 0.5
    done
    if running; then
        echo "پاسخ نداد، kill -9 می‌زنم…"
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "پنل متوقف شد."
}

case "${1:-}" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; start ;;
    status)
        if running; then
            echo "در حال اجرا — PID $(cat "$PID_FILE")"
        else
            echo "متوقف"
            exit 1
        fi
        ;;
    logs)    tail -f "$LOG_FILE" ;;
    *)
        echo "استفاده: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
