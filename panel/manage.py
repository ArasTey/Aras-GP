"""Command-line management for the panel — used by ``scripts/aras.sh``.

Kept separate from the server entry point (``python -m panel``) so the shell
menu can set a password or read settings without starting Flask. Importing
``panel`` first puts ``engine/`` on ``sys.path`` and pins the version, so the
store and the password hasher resolve the same way the running panel does.

Commands::

    python -m panel.manage set-password <password>
    python -m panel.manage info          # machine-readable key=value lines
"""

from __future__ import annotations

import argparse
import os
import sys

import panel                       # sets up engine on sys.path
from panel import paths, security, store   # noqa: E402


MIN_PASSWORD = 10


def _set_password(args: argparse.Namespace) -> int:
    password = args.password
    if password is None:
        # Read from stdin so the shell never puts the password in argv, where
        # it would show up in `ps` and the shell history.
        password = sys.stdin.readline().rstrip("\n")
    if len(password) < MIN_PASSWORD:
        print(f"Password must be at least {MIN_PASSWORD} characters.",
              file=sys.stderr)
        return 1
    security.set_admin_password(password)
    print("Panel password updated.")
    return 0


def _info(_args: argparse.Namespace) -> int:
    """Everything the menu's 'view settings' needs, one key=value per line."""
    state = store.load()
    settings = state.get("settings") or {}
    lines = {
        "version": panel.__version__,
        "admin_configured": "yes" if security.admin_configured() else "no",
        "data_dir": paths.DATA_DIR,
        "config_present": "yes" if os.path.exists(paths.CONFIG_FILE) else "no",
        "config_file": paths.CONFIG_FILE,
        "ca_present": "yes" if os.path.exists(
            os.path.join(paths.CA_DIR, "ca.crt")) else "no",
        "auto_start_relay": "yes" if settings.get("auto_start_relay") else "no",
        "relays_saved": str(len(state.get("relays") or [])),
        "friends": str(len(state.get("clients") or [])),
    }
    for key, value in lines.items():
        print(f"{key}={value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="panel.manage",
                                     description="Aras-GP panel management")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("set-password", help="set the panel admin password")
    sp.add_argument("password", nargs="?",
                    help="password; omit to read one line from stdin")
    sp.set_defaults(func=_set_password)

    ip = sub.add_parser("info", help="print current settings as key=value lines")
    ip.set_defaults(func=_info)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
