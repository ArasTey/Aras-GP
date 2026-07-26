"""The people a share config is issued to.

Just the list: names, UUIDs, and whether each is enabled. Turning that list
into configs is :mod:`share.subscription`, and putting them on Cloudflare is
:mod:`share.worker` — this module knows nothing about either.

It never touches config.json. These are Worker-side identities, not relay
accounts, so it reads and writes only the panel state through :mod:`store`.
"""

from __future__ import annotations

import re
import secrets
import time
import uuid as _uuid

from . import store

#: Friend names are labels, not identifiers. Persian writes a half-space
#: (U+200C ZWNJ) inside ordinary words, so rejecting it would reject normal
#: names. It is spelled as an escape rather than typed literally: an invisible
#: character in source cannot be reviewed, and bidi controls in particular are
#: how source is made to read differently from what it does. U+200F (RLM) used
#: to be in here too and is gone — it is a display control, never part of a name.
NAME_RE = re.compile("^[\\w .\\-()\u200c\u0622-\u06cc\u0621\u0624\u0626\u0654]{1,40}$", re.UNICODE)

class ClientError(ValueError):
    """Raised with a Persian, user-facing message."""


# ── the client list ────────────────────────────────────────────────────

def list_clients() -> list[dict]:
    clients = store.load().get("clients") or []
    return [c for c in clients if isinstance(c, dict)]


def uuids() -> list[str]:
    """Every enabled client's UUID — what the Worker is told to accept.

    Empty while the share feature is off, which is the default. The Worker
    refuses every client on an empty binding, so off here is off there — the
    VLESS server does not exist until the operator has turned it on and
    deployed deliberately.

    The switch is read here rather than at the call sites because this is the
    single value the Worker's behaviour derives from; gating anywhere else
    would leave a path that still armed it.
    """
    share = store.load().get("share") or {}
    if not share.get("enabled"):
        return []
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


