#!/usr/bin/env bash
# Aras-GP one-click launcher (Linux / macOS).
#
#   ./run.sh              start the relay engine
#   ./run.sh panel        start the control panel  (http://127.0.0.1:8600)
#   ./run.sh <args...>    any main.py flag, e.g. --install-cert, --scan
#
# Creates a local virtualenv, installs every dependency, runs the setup
# wizard if there is no config yet, then starts what you asked for.

set -e
cd "$(dirname "$0")"

VENV_DIR=".venv"

find_python() {
    for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            ver=$("$cmd" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo "0.0")
            major=${ver%.*}; minor=${ver#*.}
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PY=$(find_python) || {
    echo "[X] Python 3.10+ not found. Install it and re-run this script." >&2
    exit 1
}

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[*] Creating virtual environment in $VENV_DIR ..."
    "$PY" -m venv "$VENV_DIR"
fi

VPY="$VENV_DIR/bin/python"

# requirements.txt now covers the panel as well as the engine. It did not, and
# a virtualenv built here came out without Flask in it — so the launcher
# reported success and `python -m panel` then failed on an import.
echo "[*] Installing dependencies ..."
"$VPY" -m pip install --disable-pip-version-check -q --upgrade pip >/dev/null
if ! "$VPY" -m pip install --disable-pip-version-check -q -r requirements.txt; then
    echo "[X] Could not install dependencies. Check your network and retry." >&2
    exit 1
fi

# The panel builds its own config through the browser, and the certificate
# commands run standalone, so neither should be ambushed by the wizard.
case " $* " in
    *" panel "*|*-cert*) needs_config="" ;;
    *)                   needs_config="1" ;;
esac
if [ -n "$needs_config" ] && [ ! -f "config.json" ]; then
    echo "[*] No config.json found — launching setup wizard ..."
    "$VPY" setup.py
fi

if [ "$1" = "panel" ]; then
    shift
    echo
    echo "[*] Starting the Aras-GP panel  ->  http://127.0.0.1:${ARAS_PANEL_PORT:-8600}"
    echo
    exec "$VPY" -m panel "$@"
fi

echo
echo "[*] Starting Aras-GP ..."
echo
exec "$VPY" main.py "$@"
