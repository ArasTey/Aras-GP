"""Authentication, CSRF and rate limiting for the panel itself.

The panel holds the relay's ``auth_key`` and — if the operator opts in — a
Cloudflare API token. It is therefore treated as a privileged surface: every
page except the login and first-run setup requires a session, every state
changing request carries a CSRF token, and the endpoints that talk to third
parties or check passwords are rate limited.
"""

from __future__ import annotations

import hmac
import ipaddress
import logging
import secrets
import time
from functools import wraps

from flask import flash, g, jsonify, redirect, request, session, url_for

from account_manager import hash_password, verify_password  # from engine/
from . import store

log = logging.getLogger("panel.security")

SESSION_USER_KEY = "aras_admin"
SESSION_CSRF_KEY = "aras_csrf"
SESSION_STARTED_KEY = "aras_started"

# Sessions are short by design: the panel is a local admin tool, not a portal.
SESSION_MAX_AGE = 12 * 3600

# Values that must never reach a log line or an API response.
_SECRET_FIELD_MARKERS = ("token", "password", "auth_key", "secret", "key")


# ── admin credential ──────────────────────────────────────────────────


def admin_configured() -> bool:
    return bool((store.load().get("admin") or {}).get("hash"))


def set_admin_password(password: str) -> None:
    store.update(admin=hash_password(password))


def check_admin_password(password: str) -> bool:
    record = store.load().get("admin") or {}
    if not record.get("hash"):
        return False
    return verify_password(record, password)


def get_secret_key() -> bytes:
    """Stable Flask session key; generated once and kept in the private store."""
    state = store.load()
    key = state.get("secret_key")
    if not key:
        key = secrets.token_hex(32)
        store.update(secret_key=key)
    return bytes.fromhex(key)


# ── sessions ──────────────────────────────────────────────────────────


def login(remote_addr: str | None = None) -> None:
    session.clear()
    session[SESSION_USER_KEY] = True
    session[SESSION_STARTED_KEY] = time.time()
    session[SESSION_CSRF_KEY] = secrets.token_urlsafe(32)
    session.permanent = False
    log.info("Panel login from %s", remote_addr or "unknown")


def logout() -> None:
    session.clear()


def is_authenticated() -> bool:
    if not session.get(SESSION_USER_KEY):
        return False
    started = session.get(SESSION_STARTED_KEY) or 0
    if time.time() - started > SESSION_MAX_AGE:
        session.clear()
        return False
    return True


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not admin_configured():
            return redirect(url_for("setup"))
        if not is_authenticated():
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "unauthenticated"}), 401
            return redirect(url_for("login_view", next=request.path))
        return view(*args, **kwargs)

    return wrapper


# ── CSRF ──────────────────────────────────────────────────────────────


def csrf_token() -> str:
    token = session.get(SESSION_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_CSRF_KEY] = token
    return token


def csrf_valid() -> bool:
    expected = session.get(SESSION_CSRF_KEY)
    if not expected:
        return False
    supplied = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
        or (request.get_json(silent=True) or {}).get("csrf_token")
        or ""
    )
    return hmac.compare_digest(str(supplied), str(expected))


def enforce_csrf():
    """``before_request`` hook: reject unsafe methods without a valid token."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    if request.endpoint in ("login_view", "setup", "static"):
        return None
    if csrf_valid():
        return None
    log.warning("CSRF rejected: %s %s", request.method, request.path)
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "csrf"}), 400
    flash("درخواست نامعتبر بود (CSRF). دوباره تلاش کنید.", "error")
    return redirect(request.referrer or url_for("dashboard"))


# ── rate limiting ─────────────────────────────────────────────────────


class RateLimiter:
    """Fixed-window counter keyed by bucket + client address.

    Deliberately in-memory: the panel is a single process, and persisting
    rate-limit state would only add another file holding client addresses.
    """

    def __init__(self):
        self._hits: dict[tuple[str, str], list[float]] = {}

    def check(self, bucket: str, limit: int, window: float,
              key: str | None = None) -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)``."""
        now = time.time()
        ident = (bucket, key or client_ip())
        recent = [t for t in self._hits.get(ident, []) if now - t < window]
        if len(recent) >= limit:
            self._hits[ident] = recent
            return False, max(0.0, window - (now - recent[0]))
        recent.append(now)
        self._hits[ident] = recent
        return True, 0.0

    def reset(self, bucket: str, key: str | None = None) -> None:
        self._hits.pop((bucket, key or client_ip()), None)


limiter = RateLimiter()


def client_ip() -> str:
    """Client address. Proxy headers are ignored on purpose — the panel is
    meant to be bound to localhost, and trusting XFF here would let a remote
    caller forge its way around the login rate limit."""
    return request.remote_addr or "?"


def rate_limit(bucket: str, limit: int, window: float):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            # Only attempts count. Rate-limiting GET would lock the operator
            # out of the login *page* itself, which redirects straight back
            # into the limiter — an unrecoverable loop.
            if request.method in ("GET", "HEAD", "OPTIONS"):
                return view(*args, **kwargs)
            allowed, retry = limiter.check(bucket, limit, window)
            if not allowed:
                wait = int(retry) + 1
                if request.path.startswith("/api/"):
                    return jsonify({
                        "ok": False,
                        "error": "rate_limited",
                        "retry_after": wait,
                    }), 429
                flash(f"تعداد درخواست‌ها زیاد بود. {wait} ثانیه صبر کنید.", "error")
                # Redirect back to the same path, never to the dashboard: a
                # rate-limited POST /login bounced to / would just redirect
                # to /login again and loop.
                return redirect(request.path)
            return view(*args, **kwargs)

        return wrapper

    return decorator


# ── redaction ─────────────────────────────────────────────────────────


def redact(value: str | None, keep: int = 4) -> str:
    """Turn a secret into a display-safe fingerprint (never the value)."""
    if not value:
        return ""
    text = str(value)
    if len(text) <= keep:
        return "•" * len(text)
    return "•" * max(4, len(text) - keep) + text[-keep:]


def scrub(data):
    """Recursively redact secret-looking fields before display or logging."""
    if isinstance(data, dict):
        out = {}
        for key, value in data.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in _SECRET_FIELD_MARKERS) \
                    and isinstance(value, str):
                out[key] = redact(value)
            else:
                out[key] = scrub(value)
        return out
    if isinstance(data, list):
        return [scrub(item) for item in data]
    return data


def is_local_request() -> bool:
    """True when the caller is on the loopback interface."""
    try:
        return ipaddress.ip_address(client_ip()).is_loopback
    except ValueError:
        return False


def csp_nonce() -> str:
    """Per-response nonce for the page's inline <script> blocks.

    The panel keeps ``script-src 'self'`` — no ``'unsafe-inline'`` — so each
    page's inline bootstrap has to carry a nonce. Weakening the policy instead
    would defeat the point of having one on a surface that holds API tokens.
    """
    nonce = getattr(g, "_csp_nonce", None)
    if nonce is None:
        nonce = secrets.token_urlsafe(16)
        g._csp_nonce = nonce
    return nonce


def set_security_headers(response):
    """Conservative headers. The panel ships no third-party assets, so the
    CSP can forbid every external origin outright."""
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        f"script-src 'self' 'nonce-{csp_nonce()}'; font-src 'self'; connect-src 'self'; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    return response


def register(app):
    """Wire the session cookie policy and hooks onto a Flask app."""
    app.secret_key = get_secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="aras_gp_session",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    app.before_request(enforce_csrf)
    app.after_request(set_security_headers)

    @app.context_processor
    def _inject():
        return {"csrf_token": csrf_token, "csp_nonce": csp_nonce}

    @app.before_request
    def _remember_ip():
        g.client_ip = client_ip()
