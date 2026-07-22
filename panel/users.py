"""Proxy user management (the "complete" multi-user option).

Users live in ``config.json`` under ``proxy_auth.users`` so the relay can be
started from ``main.py`` with the exact same account table the panel manages —
there is no second source of truth. Each record holds a PBKDF2 digest, a quota,
an optional expiry and the cumulative byte counters, which lets usage survive a
restart.

Whenever the table changes the panel pushes it into the live relay via
:meth:`RelayManager.sync_accounts`, so an edit takes effect immediately instead
of at the next restart.
"""

from __future__ import annotations

import re
import time

from account_manager import hash_password   # from src/
from . import store
from .relay_manager import manager

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
MIN_PASSWORD_LENGTH = 8

GIB = 1024 ** 3


class UserError(ValueError):
    """Raised with a Persian, user-facing message."""


def _section(config: dict) -> dict:
    """Return the proxy_auth block, repairing it if it was hand-edited badly.

    config.json is a file humans open. A malformed section should not take the
    users page down with a 500 — the panel rewrites it to a sane shape instead.
    """
    section = config.get("proxy_auth")
    if not isinstance(section, dict):
        section = {}
    if not isinstance(section.get("users"), list):
        section["users"] = []
    section["users"] = [u for u in section["users"] if isinstance(u, dict)]
    section.setdefault("enabled", False)
    section.setdefault("realm", "Aras-GP")
    config["proxy_auth"] = section
    return section


def _load() -> tuple[dict, dict]:
    config = store.load_config()
    if config is None:
        raise UserError("ابتدا باید کانفیگ رله را بسازید.")
    return config, _section(config)


def _persist(config: dict) -> None:
    """Save config.json and hot-reload the running relay."""
    section = _section(config)
    store.save_config(config)
    store.update(proxy_users=[
        {"username": u.get("username"), "quota_bytes": u.get("quota_bytes", 0)}
        for u in section["users"]
    ])
    if manager.running:
        manager.sync_accounts(section["users"], section["enabled"])


def auth_enabled() -> bool:
    config = store.load_config() or {}
    return bool((config.get("proxy_auth") or {}).get("enabled"))


def set_auth_enabled(enabled: bool) -> None:
    config, section = _load()
    section["enabled"] = bool(enabled)
    _persist(config)


def list_users() -> list[dict]:
    """Stored records merged with live counters from the running relay."""
    config = store.load_config() or {}
    section = _section(config)
    live = {row["username"]: row for row in manager.stats().get("accounts", [])}

    out = []
    for record in section["users"]:
        username = record.get("username", "")
        merged = {
            "username": username,
            "quota_bytes": int(record.get("quota_bytes", 0) or 0),
            "expires_at": record.get("expires_at"),
            "enabled": bool(record.get("enabled", True)),
            "note": record.get("note", ""),
            "created_at": record.get("created_at"),
            "up_bytes": int(record.get("up_bytes", 0) or 0),
            "down_bytes": int(record.get("down_bytes", 0) or 0),
            "last_seen": record.get("last_seen"),
            "connections": 0,
            "status": "disabled" if not record.get("enabled", True) else "idle",
        }
        current = live.get(username)
        if current:
            merged.update({
                "up_bytes": current["up_bytes"],
                "down_bytes": current["down_bytes"],
                "connections": current["connections"],
                "status": current["status"],
                "last_seen": current["last_seen"] or merged["last_seen"],
            })
        merged["used_bytes"] = merged["up_bytes"] + merged["down_bytes"]
        merged["remaining_bytes"] = (
            max(0, merged["quota_bytes"] - merged["used_bytes"])
            if merged["quota_bytes"] else None
        )
        merged["percent"] = (
            min(100, round(merged["used_bytes"] * 100 / merged["quota_bytes"]))
            if merged["quota_bytes"] else None
        )
        out.append(merged)
    return out


def _validate_new(username: str, password: str, existing: list[dict]) -> None:
    if not USERNAME_RE.match(str(username or "")):
        raise UserError(
            "نام کاربری باید ۳ تا ۳۲ کاراکتر و شامل حروف، عدد، نقطه، خط تیره باشد."
        )
    if any(u.get("username") == username for u in existing):
        raise UserError("این نام کاربری از قبل وجود دارد.")
    if len(str(password or "")) < MIN_PASSWORD_LENGTH:
        raise UserError(f"رمز عبور باید حداقل {MIN_PASSWORD_LENGTH} کاراکتر باشد.")


def add_user(username: str, password: str, quota_gb: float = 0,
             expires_at: str | None = None, note: str = "") -> dict:
    config, section = _load()
    username = str(username or "").strip()
    _validate_new(username, password, section["users"])

    record = {
        "username": username,
        **hash_password(password),
        "quota_bytes": int(max(0.0, float(quota_gb or 0)) * GIB),
        "expires_at": (expires_at or "").strip() or None,
        "enabled": True,
        "note": (note or "").strip(),
        "up_bytes": 0,
        "down_bytes": 0,
        "last_seen": None,
        "created_at": time.time(),
    }
    section["users"].append(record)
    _persist(config)
    return record


def update_user(username: str, password: str | None = None,
                quota_gb: float | None = None, expires_at: str | None = None,
                note: str | None = None, enabled: bool | None = None) -> None:
    config, section = _load()
    record = next((u for u in section["users"] if u.get("username") == username), None)
    if record is None:
        raise UserError("کاربر پیدا نشد.")

    if password:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise UserError(f"رمز عبور باید حداقل {MIN_PASSWORD_LENGTH} کاراکتر باشد.")
        record.update(hash_password(password))
    if quota_gb is not None:
        record["quota_bytes"] = int(max(0.0, float(quota_gb or 0)) * GIB)
    if expires_at is not None:
        record["expires_at"] = (expires_at or "").strip() or None
    if note is not None:
        record["note"] = note.strip()
    if enabled is not None:
        record["enabled"] = bool(enabled)

    _persist(config)
    if enabled is False and manager.running:
        manager.disconnect_user(username)


def delete_user(username: str) -> None:
    config, section = _load()
    before = len(section["users"])
    section["users"] = [u for u in section["users"] if u.get("username") != username]
    if len(section["users"]) == before:
        raise UserError("کاربر پیدا نشد.")
    _persist(config)
    if manager.running:
        manager.disconnect_user(username)


def reset_usage(username: str) -> None:
    config, section = _load()
    record = next((u for u in section["users"] if u.get("username") == username), None)
    if record is None:
        raise UserError("کاربر پیدا نشد.")
    record["up_bytes"] = 0
    record["down_bytes"] = 0
    if manager.running:
        manager.reset_user_usage(username)
    _persist(config)


def disconnect(username: str) -> int:
    if not manager.running:
        raise UserError("رله در حال اجرا نیست.")
    return manager.disconnect_user(username)


def persist_live_usage() -> None:
    """Fold the relay's in-memory counters back into config.json.

    Wired to :attr:`RelayManager.sample_hook` in ``create_app`` so it also runs
    every ``PERSIST_EVERY`` seconds while the relay is up, not only on a clean
    shutdown. Writes nothing when no counter moved.
    """
    if not manager.running:
        return
    live = {row["username"]: row for row in manager.stats().get("accounts", [])}
    if not live:
        return
    try:
        config, section = _load()
    except UserError:
        return
    changed = False
    for record in section["users"]:
        current = live.get(record.get("username"))
        if not current:
            continue
        if (record.get("up_bytes") != current["up_bytes"]
                or record.get("down_bytes") != current["down_bytes"]):
            record["up_bytes"] = current["up_bytes"]
            record["down_bytes"] = current["down_bytes"]
            record["last_seen"] = current["last_seen"]
            changed = True
    if changed:
        store.save_config(config)


def client_settings(username: str) -> dict:
    """Connection details to hand to a user (no password — panel shows it once)."""
    config = store.load_config() or {}
    host = config.get("listen_host", "127.0.0.1")
    return {
        "http_host": host,
        "http_port": config.get("listen_port", 8085),
        "socks5_enabled": config.get("socks5_enabled", True),
        "socks5_port": config.get("socks5_port", 1080),
        "username": username,
    }
