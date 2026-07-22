"""Per-connection accounts for the local proxy (Aras-GP Panel).

The upstream relay is a single-user personal proxy: anyone able to reach the
listener can use it. That is fine on 127.0.0.1, but as soon as ``lan_sharing``
opens the listener on 0.0.0.0 there is no way to tell one client from another,
and no way to bound how much traffic any of them uses.

This module adds that missing layer:

* **Authentication** — HTTP proxy clients authenticate with ``Proxy-Authorization:
  Basic`` (RFC 7235), SOCKS5 clients with username/password (RFC 1929).
* **Accounting** — every byte that crosses a client socket is attributed to the
  account that opened it.
* **Enforcement** — when an account passes its quota or its expiry date, new
  connections are refused *and* its live connections are torn down.

It is entirely opt-in. Without ``proxy_auth.enabled`` the manager reports
``required = False`` and :class:`~proxy_server.ProxyServer` behaves exactly as
it did before, so a plain personal setup is unaffected.

Passwords are never stored in the clear: each account keeps a PBKDF2-HMAC-SHA256
digest with a per-account salt. Because proxy clients re-authenticate on every
new connection, a verified password is memoised as an HMAC in memory so the
KDF runs once per credential rather than once per connection.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import logging
import secrets
import time
from datetime import datetime, timezone

log = logging.getLogger("Accounts")

PBKDF2_ITERATIONS = 120_000
_SALT_BYTES = 16
_DIGEST = "sha256"


# ── password helpers ──────────────────────────────────────────────────


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> dict:
    """Return a serialisable PBKDF2 record for ``password``."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_DIGEST, password.encode("utf-8"), salt, iterations)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
        "iterations": iterations,
    }


def verify_password(record: dict, password: str) -> bool:
    """Constant-time check of ``password`` against a :func:`hash_password` record."""
    try:
        salt = base64.b64decode(record["salt"])
        expected = base64.b64decode(record["hash"])
        iterations = int(record.get("iterations", PBKDF2_ITERATIONS))
    except (KeyError, TypeError, ValueError, binascii.Error):
        return False
    candidate = hashlib.pbkdf2_hmac(_DIGEST, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def _parse_expiry(value) -> float | None:
    """Accept an ISO-8601 date/datetime or epoch seconds; return epoch or None."""
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        if len(text) == 10:  # YYYY-MM-DD → end of that day, UTC
            dt = datetime.strptime(text, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        log.warning("Ignoring unparsable expiry value: %r", value)
        return None


# ── account ───────────────────────────────────────────────────────────


class Account:
    """One proxy user: credentials, quota, live counters and open connections."""

    __slots__ = (
        "username", "_secret", "quota_bytes", "expires_at", "enabled", "note",
        "up_bytes", "down_bytes", "last_seen", "created_at",
        "_conns", "_verified_token",
    )

    def __init__(self, record: dict):
        self.username: str = str(record.get("username", "")).strip()
        self._secret: dict = {
            "salt": record.get("salt", ""),
            "hash": record.get("hash", ""),
            "iterations": record.get("iterations", PBKDF2_ITERATIONS),
        }
        self.quota_bytes: int = max(0, int(record.get("quota_bytes", 0) or 0))
        self.expires_at: float | None = _parse_expiry(record.get("expires_at"))
        self.enabled: bool = bool(record.get("enabled", True))
        self.note: str = str(record.get("note", "") or "")

        self.up_bytes: int = max(0, int(record.get("up_bytes", 0) or 0))
        self.down_bytes: int = max(0, int(record.get("down_bytes", 0) or 0))
        self.last_seen: float | None = record.get("last_seen") or None
        self.created_at: float = float(record.get("created_at") or time.time())

        self._conns: set[asyncio.Task] = set()
        self._verified_token: bytes | None = None

    # -- state ---------------------------------------------------------

    @property
    def used_bytes(self) -> int:
        return self.up_bytes + self.down_bytes

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and time.time() > self.expires_at

    @property
    def over_quota(self) -> bool:
        return self.quota_bytes > 0 and self.used_bytes >= self.quota_bytes

    @property
    def active(self) -> bool:
        """True when this account may open a new connection right now."""
        return self.enabled and not self.expired and not self.over_quota

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.expired:
            return "expired"
        if self.over_quota:
            return "quota"
        return "active"

    # -- credentials ---------------------------------------------------

    def _token_for(self, password: str) -> bytes:
        """Cheap keyed digest used to memoise an already-verified password."""
        salt = self._secret.get("salt", "").encode("ascii", "ignore")
        return hmac.new(salt, password.encode("utf-8"), _DIGEST).digest()

    def check_password(self, password: str) -> bool:
        token = self._token_for(password)
        cached = self._verified_token
        if cached is not None and hmac.compare_digest(cached, token):
            return True
        if verify_password(self._secret, password):
            self._verified_token = token
            return True
        return False

    def update_secret(self, record: dict) -> None:
        new = {
            "salt": record.get("salt", ""),
            "hash": record.get("hash", ""),
            "iterations": record.get("iterations", PBKDF2_ITERATIONS),
        }
        if new != self._secret:
            self._secret = new
            self._verified_token = None  # force a fresh KDF run

    # -- accounting ----------------------------------------------------

    def add_up(self, n: int) -> None:
        if n > 0:
            self.up_bytes += n
            self.last_seen = time.time()

    def add_down(self, n: int) -> None:
        if n > 0:
            self.down_bytes += n
            self.last_seen = time.time()

    # -- connections ---------------------------------------------------

    def attach(self, task: asyncio.Task | None) -> None:
        if task is not None:
            self._conns.add(task)

    def detach(self, task: asyncio.Task | None) -> None:
        self._conns.discard(task)

    @property
    def connections(self) -> int:
        return len(self._conns)

    def disconnect_all(self) -> int:
        """Cancel every live connection belonging to this account."""
        tasks = [t for t in self._conns if not t.done()]
        for task in tasks:
            task.cancel()
        self._conns.clear()
        return len(tasks)

    # -- serialisation -------------------------------------------------

    def to_record(self) -> dict:
        """Full record, credentials included — for config.json persistence."""
        return {
            "username": self.username,
            "salt": self._secret.get("salt", ""),
            "hash": self._secret.get("hash", ""),
            "iterations": self._secret.get("iterations", PBKDF2_ITERATIONS),
            "quota_bytes": self.quota_bytes,
            "expires_at": self.expires_at,
            "enabled": self.enabled,
            "note": self.note,
            "up_bytes": self.up_bytes,
            "down_bytes": self.down_bytes,
            "last_seen": self.last_seen,
            "created_at": self.created_at,
        }

    def to_public(self) -> dict:
        """Credential-free view — safe to send to the panel UI."""
        return {
            "username": self.username,
            "quota_bytes": self.quota_bytes,
            "used_bytes": self.used_bytes,
            "up_bytes": self.up_bytes,
            "down_bytes": self.down_bytes,
            "remaining_bytes": (
                max(0, self.quota_bytes - self.used_bytes) if self.quota_bytes else None
            ),
            "expires_at": self.expires_at,
            "enabled": self.enabled,
            "note": self.note,
            "status": self.status(),
            "connections": self.connections,
            "last_seen": self.last_seen,
            "created_at": self.created_at,
        }


# ── manager ───────────────────────────────────────────────────────────


class AccountManager:
    """Owns the account table and answers auth questions for the listeners."""

    def __init__(self, config: dict):
        section = config.get("proxy_auth")
        if not isinstance(section, dict):
            # A hand-edited config.json must not stop the relay from booting.
            if section is not None:
                log.warning("Ignoring malformed 'proxy_auth' section (%s)",
                            type(section).__name__)
            section = {}
        self.required: bool = bool(section.get("enabled", False))
        self.realm: str = str(section.get("realm") or "Aras-GP")
        self._accounts: dict[str, Account] = {}
        self.load(section.get("users"))
        if self.required:
            log.info("Per-user proxy authentication ENABLED (%d account(s))",
                     len(self._accounts))

    # -- table ---------------------------------------------------------

    def load(self, records) -> None:
        """Replace the table, preserving live counters for surviving users."""
        if not isinstance(records, list):
            if records:
                log.warning("Ignoring malformed 'proxy_auth.users' (%s)",
                            type(records).__name__)
            records = []
        seen = set()
        for record in records:
            if not isinstance(record, dict):
                log.warning("Skipping malformed user entry (%s)", type(record).__name__)
                continue
            username = str(record.get("username", "")).strip()
            if not username:
                continue
            seen.add(username)
            existing = self._accounts.get(username)
            if existing is None:
                self._accounts[username] = Account(record)
                continue
            # Hot-reload: keep counters and open connections, refresh policy.
            existing.update_secret(record)
            existing.quota_bytes = max(0, int(record.get("quota_bytes", 0) or 0))
            existing.expires_at = _parse_expiry(record.get("expires_at"))
            existing.enabled = bool(record.get("enabled", True))
            existing.note = str(record.get("note", "") or "")
            if "up_bytes" in record:
                existing.up_bytes = max(existing.up_bytes,
                                        int(record.get("up_bytes") or 0))
            if "down_bytes" in record:
                existing.down_bytes = max(existing.down_bytes,
                                          int(record.get("down_bytes") or 0))
        for username in list(self._accounts):
            if username not in seen:
                self._accounts.pop(username).disconnect_all()

    def set_required(self, required: bool) -> None:
        self.required = bool(required)

    def get(self, username: str) -> Account | None:
        return self._accounts.get(username)

    def __len__(self) -> int:
        return len(self._accounts)

    # -- auth ----------------------------------------------------------

    def authenticate(self, username: str, password: str) -> Account | None:
        """Return the account when the credentials are valid *and* usable."""
        account = self._accounts.get((username or "").strip())
        if account is None:
            # Burn a comparable amount of time so a missing user is not
            # distinguishable from a wrong password by timing alone.
            hashlib.pbkdf2_hmac(_DIGEST, (password or "").encode("utf-8"),
                                b"aras-gp-decoy", 1000)
            return None
        if not account.check_password(password or ""):
            return None
        if not account.active:
            log.info("Rejected %s: account is %s", account.username, account.status())
            return None
        return account

    def authenticate_basic(self, header_value: str) -> Account | None:
        """Validate a ``Basic base64(user:pass)`` credential string."""
        if not header_value:
            return None
        scheme, _, payload = header_value.strip().partition(" ")
        if scheme.lower() != "basic" or not payload:
            return None
        try:
            decoded = base64.b64decode(payload.strip(), validate=True).decode(
                "utf-8", errors="replace"
            )
        except (binascii.Error, ValueError):
            return None
        username, sep, password = decoded.partition(":")
        if not sep:
            return None
        return self.authenticate(username, password)

    # -- enforcement ---------------------------------------------------

    def enforce(self, account: Account) -> bool:
        """Drop the account's connections if it just became unusable.

        Returns True when the account is still allowed to pass traffic.
        """
        if account.active:
            return True
        killed = account.disconnect_all()
        if killed:
            log.warning("Cut off %s (%s) — %d connection(s) closed",
                        account.username, account.status(), killed)
        return False

    def sweep(self) -> list[str]:
        """Disconnect every account that is no longer active. Returns usernames."""
        cut = []
        for account in self._accounts.values():
            if not account.active and account.connections:
                account.disconnect_all()
                cut.append(account.username)
        return cut

    # -- views ---------------------------------------------------------

    def snapshot(self) -> list[dict]:
        return [a.to_public() for a in self._accounts.values()]

    def records(self) -> list[dict]:
        return [a.to_record() for a in self._accounts.values()]

    def totals(self) -> dict:
        accounts = list(self._accounts.values())
        return {
            "accounts": len(accounts),
            "active": sum(1 for a in accounts if a.active),
            "connections": sum(a.connections for a in accounts),
            "up_bytes": sum(a.up_bytes for a in accounts),
            "down_bytes": sum(a.down_bytes for a in accounts),
        }

    def reset_usage(self, username: str) -> bool:
        account = self._accounts.get(username)
        if account is None:
            return False
        account.up_bytes = 0
        account.down_bytes = 0
        return True


# ── byte-counting stream wrappers ─────────────────────────────────────
#
# These are transparent proxies around asyncio's StreamReader/StreamWriter.
# Attribute reads *and writes* are forwarded to the wrapped object, which
# matters because ProxyServer swaps `writer._transport` in place after a
# start_tls() upgrade — the assignment has to land on the real writer.


class CountedReader:
    """StreamReader proxy that attributes everything read to an account."""

    def __init__(self, reader, account: Account):
        object.__setattr__(self, "_reader", reader)
        object.__setattr__(self, "_account", account)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_reader"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_reader"), name, value)

    async def read(self, n=-1):
        data = await self._reader.read(n)
        self._account.add_up(len(data))
        return data

    async def readline(self):
        data = await self._reader.readline()
        self._account.add_up(len(data))
        return data

    async def readexactly(self, n):
        try:
            data = await self._reader.readexactly(n)
        except asyncio.IncompleteReadError as exc:
            self._account.add_up(len(exc.partial))
            raise
        self._account.add_up(len(data))
        return data

    async def readuntil(self, separator=b"\n"):
        data = await self._reader.readuntil(separator)
        self._account.add_up(len(data))
        return data


class CountedWriter:
    """StreamWriter proxy that attributes everything written to an account."""

    def __init__(self, writer, account: Account):
        object.__setattr__(self, "_writer", writer)
        object.__setattr__(self, "_account", account)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_writer"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_writer"), name, value)

    def write(self, data):
        self._account.add_down(len(data))
        return self._writer.write(data)

    def writelines(self, data):
        chunks = list(data)
        self._account.add_down(sum(len(c) for c in chunks))
        return self._writer.writelines(chunks)
