"""Small durable JSON store for panel state.

Two rules the rest of the panel relies on:

* writes are **atomic** — a crash mid-save never leaves a truncated file that
  would lock the operator out of their own panel;
* files holding secrets are created ``0600`` **before** anything is written to
  them, so there is no window where another local user can read them.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time

from . import paths

_LOCK = threading.RLock()

DEFAULT_STATE: dict = {
    "version": 1,
    "created_at": None,
    "admin": None,             # {"salt","hash","iterations"} once set up
    "secret_key": None,        # Flask session key (generated on first run)
    "settings": {
        "auto_start_relay": False,
        "remember_cloudflare_token": False,
        "chart_window": 120,
    },
    "cloudflare": {            # only populated when the operator opts in
        "account_id": "",
        "script_name": "aras-relay",
        "token": "",
        "workers_subdomain": "",
        "worker_url": "",
        "upstream_forwarder_url": "",
    },
    "gas": {
        "deployment_ids": [],
        "last_generated_at": None,
    },
    "deploy_history": [],      # newest first, capped
    "proxy_users": [],         # mirror of config.json proxy_auth.users
}

MAX_HISTORY = 50


def _write_private(path: str, payload: str) -> None:
    """Atomically write ``payload`` to ``path`` with owner-only permissions."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json_private(path: str, data, indent: int = 2) -> None:
    """Public helper: dump ``data`` as private JSON (used for config.json too)."""
    _write_private(path, json.dumps(data, indent=indent, ensure_ascii=False) + "\n")


def _merge_defaults(state: dict) -> dict:
    merged = json.loads(json.dumps(DEFAULT_STATE))
    for key, value in (state or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def load() -> dict:
    """Read panel state, filling in any keys added by a newer panel version."""
    with _LOCK:
        paths.ensure_dirs()
        try:
            with open(paths.PANEL_STATE_FILE, encoding="utf-8") as handle:
                state = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError):
            state = {}
        return _merge_defaults(state)


def save(state: dict) -> None:
    with _LOCK:
        paths.ensure_dirs()
        if not state.get("created_at"):
            state["created_at"] = time.time()
        history = state.get("deploy_history") or []
        state["deploy_history"] = history[:MAX_HISTORY]
        _write_private(paths.PANEL_STATE_FILE, json.dumps(state, indent=2,
                                                          ensure_ascii=False) + "\n")


def update(**changes) -> dict:
    """Shallow-merge ``changes`` into the stored state and persist it."""
    with _LOCK:
        state = load()
        for key, value in changes.items():
            if isinstance(value, dict) and isinstance(state.get(key), dict):
                state[key].update(value)
            else:
                state[key] = value
        save(state)
        return state


def add_history(entry: dict) -> None:
    """Record a deploy attempt. Callers must pass redacted values only."""
    with _LOCK:
        state = load()
        entry = dict(entry)
        entry.setdefault("at", time.time())
        state["deploy_history"].insert(0, entry)
        save(state)


# ── relay config.json ─────────────────────────────────────────────────


def load_config() -> dict | None:
    try:
        with open(paths.CONFIG_FILE, encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_config(config: dict) -> None:
    """Persist config.json — it holds auth_key, so it is written 0600."""
    with _LOCK:
        write_json_private(paths.CONFIG_FILE, config)


def load_example_config() -> dict:
    with open(paths.CONFIG_EXAMPLE_FILE, encoding="utf-8") as handle:
        return json.load(handle)


# ── config profiles ───────────────────────────────────────────────────


def _profile_path(name: str) -> str:
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "-_ ").strip()
    if not safe:
        raise ValueError("empty profile name")
    return os.path.join(paths.PROFILES_DIR, f"{safe}.json")


def list_profiles() -> list[dict]:
    paths.ensure_dirs()
    out = []
    for filename in sorted(os.listdir(paths.PROFILES_DIR)):
        if not filename.endswith(".json"):
            continue
        full = os.path.join(paths.PROFILES_DIR, filename)
        try:
            stat = os.stat(full)
        except OSError:
            continue
        out.append({"name": filename[:-5], "modified": stat.st_mtime,
                    "size": stat.st_size})
    return out


def save_profile(name: str, config: dict) -> None:
    with _LOCK:
        paths.ensure_dirs()
        write_json_private(_profile_path(name), config)


def load_profile(name: str) -> dict | None:
    try:
        with open(_profile_path(name), encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


def delete_profile(name: str) -> bool:
    try:
        os.unlink(_profile_path(name))
        return True
    except (OSError, ValueError):
        return False
