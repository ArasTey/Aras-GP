"""Friends / VLESS clients — the "share a config" feature.

The panel has no VPS, so the Cloudflare Worker it already deploys doubles as a
VLESS server (see ``deploy/cloudflare-worker/worker.js``). Each friend gets a
UUID here; the panel binds the whole set to the Worker at deploy time, hands
each friend a ``vless://`` link and a QR code, and serves one subscription URL
that a phone app refreshes on its own.

Why VLESS-over-WebSocket and not the SOCKS5 accounts the relay already has:
a friend's phone reaches ``<worker>.workers.dev`` from anywhere, through
Cloudflare, with no port-forward and behind CGNAT — which a home machine's
SOCKS5 port cannot offer. The trade-off is that this rides on Cloudflare
Workers, whose terms of service disallow general proxying; see the panel's
warning. It is the only architecture that satisfies "real VLESS + mobile +
no VPS", so it is the one offered, with the risk stated plainly.

This module owns the client list and the link/subscription rendering. It never
touches config.json — VLESS clients are Worker-side, not relay accounts — so it
reads and writes only the panel state through :mod:`store`.
"""

from __future__ import annotations

import base64
import re
import secrets
import time
import uuid as _uuid
from urllib.parse import quote, urlparse

from . import store

NAME_RE = re.compile(r"^[\w .\-()آ-یءؤئ]{1,40}$", re.UNICODE)

#: Default VLESS WebSocket path if the operator has not chosen one.
DEFAULT_PATH = "/aras"


class ClientError(ValueError):
    """Raised with a Persian, user-facing message."""


# ── state helpers ──────────────────────────────────────────────────────

def _vless_settings() -> dict:
    state = store.load()
    section = state.get("vless")
    if not isinstance(section, dict):
        section = {}
    section.setdefault("enabled", False)
    section.setdefault("path", DEFAULT_PATH)
    # A subscription token is minted the first time it is needed and then kept,
    # so an existing friend's subscription URL does not rotate out from under
    # them every time the panel restarts.
    if not section.get("sub_token"):
        section["sub_token"] = secrets.token_urlsafe(16)
        store.update(vless=section)
    return section


def settings() -> dict:
    section = _vless_settings()
    return {
        "enabled": bool(section.get("enabled")),
        "path": _normalize_path(section.get("path")),
        "sub_token": section.get("sub_token", ""),
    }


def set_enabled(enabled: bool) -> None:
    section = _vless_settings()
    section["enabled"] = bool(enabled)
    store.update(vless=section)


def set_path(path: str) -> str:
    path = _normalize_path(path)
    section = _vless_settings()
    section["path"] = path
    store.update(vless=section)
    return path


def _normalize_path(path) -> str:
    path = str(path or "").strip()
    if not path:
        return DEFAULT_PATH
    if not path.startswith("/"):
        path = "/" + path
    # A path is part of a URL; keep it to characters that survive one intact.
    if not re.fullmatch(r"/[\w\-./]{0,63}", path):
        return DEFAULT_PATH
    return path


# ── the client list ────────────────────────────────────────────────────

def list_clients() -> list[dict]:
    clients = store.load().get("clients") or []
    return [c for c in clients if isinstance(c, dict)]


def uuids() -> list[str]:
    """Every enabled client's UUID — what the Worker is told to accept."""
    return [c["uuid"] for c in list_clients()
            if c.get("enabled", True) and c.get("uuid")]


def add_client(name: str, note: str = "") -> dict:
    name = str(name or "").strip()
    if not NAME_RE.match(name):
        raise ClientError("نام باید ۱ تا ۴۰ کاراکتر باشد (حروف، عدد، فاصله، خط تیره).")
    clients = list_clients()
    if any(c.get("name") == name for c in clients):
        raise ClientError("این نام از قبل استفاده شده است.")
    record = {
        "id": secrets.token_hex(6),
        "name": name,
        "uuid": str(_uuid.uuid4()),
        "enabled": True,
        "note": str(note or "").strip(),
        "created_at": time.time(),
    }
    clients.append(record)
    store.update(clients=clients)
    return record


def update_client(client_id: str, name: str | None = None,
                  enabled: bool | None = None, note: str | None = None) -> dict:
    clients = list_clients()
    record = next((c for c in clients if c.get("id") == client_id), None)
    if record is None:
        raise ClientError("این دوست پیدا نشد.")
    if name is not None:
        name = str(name).strip()
        if not NAME_RE.match(name):
            raise ClientError("نام نامعتبر است.")
        if any(c.get("name") == name and c.get("id") != client_id for c in clients):
            raise ClientError("این نام از قبل استفاده شده است.")
        record["name"] = name
    if enabled is not None:
        record["enabled"] = bool(enabled)
    if note is not None:
        record["note"] = str(note).strip()
    store.update(clients=clients)
    return record


def delete_client(client_id: str) -> None:
    clients = list_clients()
    remaining = [c for c in clients if c.get("id") != client_id]
    if len(remaining) == len(clients):
        raise ClientError("این دوست پیدا نشد.")
    store.update(clients=remaining)


def rotate_uuid(client_id: str) -> dict:
    """Give a client a fresh UUID — instantly revokes the old link."""
    clients = list_clients()
    record = next((c for c in clients if c.get("id") == client_id), None)
    if record is None:
        raise ClientError("این دوست پیدا نشد.")
    record["uuid"] = str(_uuid.uuid4())
    store.update(clients=clients)
    return record


# ── link + subscription rendering ──────────────────────────────────────

def _worker_host() -> str:
    """Bare hostname of the deployed Worker, or '' if none yet."""
    url = (store.load().get("cloudflare") or {}).get("worker_url") or ""
    if not url:
        return ""
    return urlparse(url).hostname or ""


def vless_link(client: dict, host: str = "", path: str = "") -> str:
    """A ``vless://`` share link for one client.

    ws + TLS to the Worker's own domain, with host and SNI set to it too, which
    is exactly what a ``workers.dev`` deployment terminates. The fragment is the
    friend's name, so it shows up labelled in their app.
    """
    host = host or _worker_host()
    if not host or not client.get("uuid"):
        return ""
    path = _normalize_path(path or settings()["path"])
    query = (
        "encryption=none"
        "&security=tls"
        "&sni=" + quote(host) +
        "&type=ws"
        "&host=" + quote(host) +
        "&path=" + quote(path, safe="") +
        "&fp=chrome"
    )
    label = quote(client.get("name") or "aras", safe="")
    return f"vless://{client['uuid']}@{host}:443?{query}#{label}"


def all_links(host: str = "", path: str = "") -> list[str]:
    host = host or _worker_host()
    path = path or settings()["path"]
    out = []
    for client in list_clients():
        if not client.get("enabled", True):
            continue
        link = vless_link(client, host=host, path=path)
        if link:
            out.append(link)
    return out


def subscription(host: str = "", path: str = "") -> str:
    """The base64 blob a phone app expects behind a subscription URL."""
    body = "\n".join(all_links(host=host, path=path))
    return base64.b64encode(body.encode("utf-8")).decode("ascii")


def subscription_url(base_url: str) -> str:
    """Absolute subscription URL to show the operator.

    Rewritten to the machine's LAN address when the panel was opened on
    loopback: a phone typing ``127.0.0.1`` reaches itself, not the panel, so
    the copyable address has to be the one another device can actually dial.
    Guarded by the token, so knowing the path is not enough to pull the
    friends' UUIDs.
    """
    token = settings()["sub_token"]
    base = base_url.rstrip("/")
    parsed = urlparse(base)
    if parsed.hostname in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        lan = _lan_ip()
        if lan:
            port = f":{parsed.port}" if parsed.port else ""
            base = f"{parsed.scheme}://{lan}{port}"
    return f"{base}/sub/{token}"


def _lan_ip() -> str:
    """This machine's LAN IPv4, or '' when it cannot be determined."""
    try:
        from lan_utils import _primary_ipv4      # from engine/
        return _primary_ipv4() or ""
    except Exception:
        return ""
