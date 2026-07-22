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
import uuid

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
    "relays": [],              # saved relays — see save_relay()
    "active_relay": None,      # id of the relay currently loaded into config
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


# ── saved relays ──────────────────────────────────────────────────────
#
# A "relay" is one complete working chain the operator has already built:
# the Cloudflare Worker, the Apps Script deployment ID(s), the shared
# auth_key and the fronting settings. Deploying that chain is the slowest
# part of setup, so once it works it is worth keeping: switching back to a
# saved relay later is a single click instead of a redeploy.
#
# Relays are stored inside panel.json (mode 0600) because they carry the
# auth_key, which is a secret shared with the operator's Apps Script.

RELAY_FIELDS = (
    "auth_key", "script_id", "script_ids", "front_domain", "google_ip",
    "parallel_relay",
)


def _relay_id() -> str:
    return uuid.uuid4().hex[:12]


def relay_from_config(config: dict, name: str, extra: dict | None = None) -> dict:
    """Build a saved-relay record out of the live config."""
    script = config.get("script_ids") or config.get("script_id") or []
    ids = script if isinstance(script, list) else ([script] if script else [])
    cloudflare = (extra or {})
    return {
        "id": _relay_id(),
        "name": name.strip() or "بدون نام",
        "created_at": time.time(),
        "auth_key": config.get("auth_key", ""),
        "script_ids": [i for i in ids if i],
        "front_domain": config.get("front_domain", "www.google.com"),
        "google_ip": config.get("google_ip", ""),
        "parallel_relay": int(config.get("parallel_relay", 1) or 1),
        "worker_url": cloudflare.get("worker_url", ""),
        "script_name": cloudflare.get("script_name", ""),
        "note": (extra or {}).get("note", ""),
    }


def list_relays() -> list[dict]:
    """Saved relays, newest first, with the auth_key redacted."""
    state = load()
    active = state.get("active_relay")
    out = []
    for relay in state.get("relays", []):
        item = dict(relay)
        key = item.pop("auth_key", "")
        item["auth_key_set"] = bool(key)
        item["active"] = item.get("id") == active
        out.append(item)
    out.sort(key=lambda r: r.get("created_at") or 0, reverse=True)
    return out


def get_relay(relay_id: str) -> dict | None:
    for relay in load().get("relays", []):
        if relay.get("id") == relay_id:
            return relay
    return None


def save_relay(record: dict) -> dict:
    """Add a relay, or update the existing one with the same script IDs.

    Re-saving after a redeploy should refresh the entry rather than pile up
    near-identical copies, so matching is by deployment IDs, not by name.
    """
    with _LOCK:
        state = load()
        relays = state.setdefault("relays", [])
        signature = sorted(record.get("script_ids") or [])
        for existing in relays:
            if sorted(existing.get("script_ids") or []) == signature and signature:
                existing.update({k: v for k, v in record.items() if k != "id"})
                state["active_relay"] = existing["id"]
                save(state)
                return existing
        relays.append(record)
        state["active_relay"] = record["id"]
        save(state)
        return record


def delete_relay(relay_id: str) -> bool:
    with _LOCK:
        state = load()
        before = len(state.get("relays", []))
        state["relays"] = [r for r in state.get("relays", [])
                           if r.get("id") != relay_id]
        if state.get("active_relay") == relay_id:
            state["active_relay"] = None
        if len(state["relays"]) == before:
            return False
        save(state)
        return True


def apply_relay(relay_id: str) -> dict | None:
    """Load a saved relay into config.json. Returns the relay or None.

    Only the relay-identifying keys are touched; ports, host policy and the
    proxy_auth user table stay exactly as the operator left them.
    """
    with _LOCK:
        relay = get_relay(relay_id)
        if relay is None:
            return None
        config = load_config() or load_example_config()

        config["auth_key"] = relay.get("auth_key", "")
        ids = [i for i in (relay.get("script_ids") or []) if i]
        config.pop("script_ids", None)
        if ids:
            config["script_id"] = ids if len(ids) > 1 else ids[0]
        config["front_domain"] = relay.get("front_domain") or config.get("front_domain")
        if relay.get("google_ip"):
            config["google_ip"] = relay["google_ip"]
        config["parallel_relay"] = max(1, min(int(relay.get("parallel_relay", 1) or 1),
                                              max(1, len(ids))))
        save_config(config)

        state = load()
        state["active_relay"] = relay_id
        if relay.get("worker_url"):
            state["cloudflare"]["worker_url"] = relay["worker_url"]
        if relay.get("script_name"):
            state["cloudflare"]["script_name"] = relay["script_name"]
        save(state)
        return relay


# ── backup / restore / reset ──────────────────────────────────────────


BACKUP_VERSION = 1


def export_backup(include_secrets: bool = True) -> dict:
    """Everything needed to rebuild this panel on another machine.

    ``include_secrets=False`` strips the auth_key, the Cloudflare token and
    the proxy users' password hashes, so the file can be shared for support
    without handing over working credentials.
    """
    state = load()
    config = load_config()

    payload = {
        "version": BACKUP_VERSION,
        "exported_at": time.time(),
        "panel_version": None,        # filled by the caller
        "settings": state.get("settings", {}),
        "relays": state.get("relays", []),
        "active_relay": state.get("active_relay"),
        "gas": state.get("gas", {}),
        "cloudflare": dict(state.get("cloudflare", {})),
        "config": config,
        "profiles": {p["name"]: load_profile(p["name"]) for p in list_profiles()},
    }

    if not include_secrets:
        payload["cloudflare"]["token"] = ""
        for relay in payload["relays"]:
            relay["auth_key"] = ""
        if payload["config"]:
            payload["config"] = dict(payload["config"])
            payload["config"]["auth_key"] = ""
            section = payload["config"].get("proxy_auth")
            if isinstance(section, dict):
                payload["config"]["proxy_auth"] = dict(section)
                payload["config"]["proxy_auth"]["users"] = [
                    {k: v for k, v in u.items() if k not in ("salt", "hash")}
                    for u in section.get("users", [])
                ]
    else:
        # The token is a live Cloudflare credential; never ship it in a file
        # the operator is likely to email around.
        payload["cloudflare"]["token"] = ""

    return payload


def import_backup(payload: dict) -> list[str]:
    """Restore a backup. Returns a list of what was restored."""
    if not isinstance(payload, dict):
        raise ValueError("فایل پشتیبان معتبر نیست.")
    if int(payload.get("version", 0)) != BACKUP_VERSION:
        raise ValueError("نسخه‌ی فایل پشتیبان پشتیبانی نمی‌شود.")

    restored = []
    with _LOCK:
        state = load()
        if isinstance(payload.get("settings"), dict):
            state["settings"].update(payload["settings"])
            restored.append("تنظیمات")
        if isinstance(payload.get("relays"), list):
            state["relays"] = payload["relays"]
            state["active_relay"] = payload.get("active_relay")
            restored.append(f"{len(payload['relays'])} رله")
        if isinstance(payload.get("gas"), dict):
            state["gas"].update(payload["gas"])
        if isinstance(payload.get("cloudflare"), dict):
            cloudflare = dict(payload["cloudflare"])
            cloudflare.pop("token", None)      # never restore a credential
            state["cloudflare"].update(cloudflare)
        save(state)

        if isinstance(payload.get("config"), dict):
            save_config(payload["config"])
            restored.append("کانفیگ رله")

        for name, config in (payload.get("profiles") or {}).items():
            if isinstance(config, dict):
                try:
                    save_profile(name, config)
                except ValueError:
                    continue
        if payload.get("profiles"):
            restored.append(f"{len(payload['profiles'])} پروفایل")

    return restored


def factory_reset(keep_admin: bool = True) -> None:
    """Delete panel state and the relay config.

    ``keep_admin`` preserves the panel password and session key so the
    operator is not logged out and locked into the first-run wizard by an
    action they took from inside the panel.
    """
    with _LOCK:
        state = load()
        admin = state.get("admin") if keep_admin else None
        secret = state.get("secret_key") if keep_admin else None

        fresh = json.loads(json.dumps(DEFAULT_STATE))
        fresh["admin"] = admin
        fresh["secret_key"] = secret
        fresh["created_at"] = time.time()
        save(fresh)

        for path in (paths.CONFIG_FILE,):
            try:
                os.unlink(path)
            except OSError:
                pass

        try:
            for filename in os.listdir(paths.PROFILES_DIR):
                if filename.endswith(".json"):
                    os.unlink(os.path.join(paths.PROFILES_DIR, filename))
        except OSError:
            pass
