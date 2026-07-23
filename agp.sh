#!/usr/bin/env bash
# Aras-GP manager launcher (Linux / macOS).
# Opens the management menu:  ./agp.sh
# Or a one-shot command:      ./agp.sh {start|stop|restart|status|install|version}
cd "$(dirname "$0")" || exit 1

for cmd in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        exec "$cmd" manage.py "$@"
    fi
done

echo "[X] Python 3.10+ not found. Install it from https://www.python.org/downloads/" >&2
exit 1
