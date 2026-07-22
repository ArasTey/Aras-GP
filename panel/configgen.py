"""Builder and validator for the relay's ``config.json``.

The field table below mirrors ``config.example.json`` exactly — same keys, same
types, same defaults — because the output of this module is fed straight to
``main.py``. Nothing here renames or reinterprets a key; the panel is a nicer
way to fill in the file the relay already understands.

The only addition is the ``proxy_auth`` block, which the panel writes for the
multi-user layer in ``src/account_manager.py``. It is namespaced under a single
new key so an older relay simply ignores it.
"""

from __future__ import annotations

import ipaddress
import re
import secrets
import string

from . import store

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$")
_SCRIPT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,120}$")

PLACEHOLDER_AUTH_KEYS = {
    "", "CHANGE_ME_TO_A_STRONG_SECRET", "your-secret-password-here",
}
PLACEHOLDER_SCRIPT_IDS = {"", "YOUR_APPS_SCRIPT_DEPLOYMENT_ID"}

MIN_AUTH_KEY_LENGTH = 16


class ConfigError(ValueError):
    """Raised with a Persian, user-facing message."""


# ── field table ───────────────────────────────────────────────────────
# (key, kind, default). ``kind`` drives coercion in :func:`build`.

FIELDS: tuple[tuple[str, str, object], ...] = (
    ("google_ip",                    "ip",     "216.239.38.120"),
    ("front_domain",                 "host",   "www.google.com"),
    ("auth_key",                     "secret", ""),
    ("listen_host",                  "text",   "127.0.0.1"),
    ("listen_port",                  "port",   8085),
    ("socks5_enabled",               "bool",   True),
    ("socks5_port",                  "port",   1080),
    ("log_level",                    "level",  "INFO"),
    ("verify_ssl",                   "bool",   True),
    ("lan_sharing",                  "bool",   True),
    ("relay_timeout",                "int",    25),
    ("tls_connect_timeout",          "int",    15),
    ("tcp_connect_timeout",          "int",    10),
    ("max_response_body_bytes",      "int",    209715200),
    ("parallel_relay",               "int",    1),
    ("chunked_download_extensions",  "list",   None),
    ("chunked_download_min_size",    "int",    5242880),
    ("chunked_download_chunk_size",  "int",    524288),
    ("chunked_download_max_parallel", "int",   8),
    ("chunked_download_max_chunks",  "int",    256),
    ("block_hosts",                  "list",   None),
    ("bypass_hosts",                 "list",   None),
    ("forwarder_hosts",              "list",   None),
    ("direct_google_exclude",        "list",   None),
    ("direct_google_allow",          "list",   None),
    ("youtube_via_relay",            "bool",   False),
)

# Sensible lower bounds — the relay itself clamps some of these, but catching
# them here turns a silent surprise into a form error the operator can see.
_MINIMUMS = {
    "relay_timeout": 5,
    "tls_connect_timeout": 3,
    "tcp_connect_timeout": 1,
    "max_response_body_bytes": 1024 * 1024,
    "parallel_relay": 1,
    "chunked_download_min_size": 0,
    "chunked_download_chunk_size": 64 * 1024,
    "chunked_download_max_parallel": 1,
    "chunked_download_max_chunks": 1,
}


def defaults() -> dict:
    """Start from the shipped example so list defaults stay in one place."""
    try:
        return store.load_example_config()
    except Exception:
        return {key: value for key, _kind, value in FIELDS if value is not None}


# ── coercion helpers ──────────────────────────────────────────────────


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "on", "yes", "بله")


def as_int(value, field: str, minimum: int | None = None) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ConfigError(f"مقدار «{field}» باید عدد صحیح باشد.")
    if minimum is not None and number < minimum:
        raise ConfigError(f"مقدار «{field}» نباید کمتر از {minimum} باشد.")
    return number


def as_port(value, field: str) -> int:
    port = as_int(value, field)
    if not 1 <= port <= 65535:
        raise ConfigError(f"پورت «{field}» باید بین ۱ تا ۶۵۵۳۵ باشد.")
    return port


def as_list(value) -> list[str]:
    """Accept a textarea (newline/comma separated) or a real list."""
    if isinstance(value, list):
        items = value
    else:
        items = re.split(r"[\n,]+", str(value or ""))
    seen, out = set(), []
    for item in items:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def as_host(value, field: str) -> str:
    host = str(value or "").strip().rstrip(".")
    if not host or not _HOSTNAME_RE.match(host):
        raise ConfigError(f"«{field}» یک نام دامنه معتبر نیست.")
    return host


def as_ip(value, field: str) -> str:
    text = str(value or "").strip()
    try:
        ipaddress.ip_address(text)
    except ValueError:
        raise ConfigError(f"«{field}» یک آدرس IP معتبر نیست.")
    return text


def parse_hosts_map(value) -> dict[str, str]:
    """Parse the DNS override map from ``domain = ip`` lines."""
    if isinstance(value, dict):
        return {str(k).strip(): str(v).strip() for k, v in value.items() if k and v}
    out: dict[str, str] = {}
    for line in str(value or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        domain, sep, ip = line.replace("\t", " ").partition("=")
        if not sep:
            parts = line.split()
            if len(parts) != 2:
                raise ConfigError(f"سطر نگاشت میزبان نامعتبر است: {line}")
            domain, ip = parts
        domain, ip = domain.strip(), ip.strip()
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            raise ConfigError(f"آدرس IP نامعتبر در نگاشت میزبان: {ip}")
        out[domain] = ip
    return out


def parse_script_ids(value) -> list[str]:
    ids = as_list(value)
    for script_id in ids:
        if script_id in PLACEHOLDER_SCRIPT_IDS:
            raise ConfigError("شناسه استقرار Apps Script هنوز پر نشده است.")
        if not _SCRIPT_ID_RE.match(script_id):
            raise ConfigError(f"شناسه استقرار نامعتبر است: {script_id[:24]}…")
    if not ids:
        raise ConfigError("حداقل یک شناسه استقرار Apps Script لازم است.")
    return ids


def generate_auth_key(length: int = 40) -> str:
    """Strong shared secret, same alphabet the CLI wizard in setup.py uses."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ── build ─────────────────────────────────────────────────────────────


def build(form: dict, base: dict | None = None) -> dict:
    """Turn submitted form values into a validated ``config.json`` dict."""
    config = dict(base or defaults())
    config["mode"] = "apps_script"   # the relay forces this anyway

    for key, kind, fallback in FIELDS:
        if key not in form:
            if key not in config and fallback is not None:
                config[key] = fallback
            continue
        raw = form[key]
        if kind == "bool":
            config[key] = as_bool(raw)
        elif kind == "port":
            config[key] = as_port(raw, key)
        elif kind == "int":
            config[key] = as_int(raw, key, _MINIMUMS.get(key))
        elif kind == "list":
            config[key] = as_list(raw)
        elif kind == "host":
            config[key] = as_host(raw, key)
        elif kind == "ip":
            config[key] = as_ip(raw, key)
        elif kind == "level":
            level = str(raw).strip().upper()
            if level not in LOG_LEVELS:
                raise ConfigError("سطح لاگ نامعتبر است.")
            config[key] = level
        elif kind == "secret":
            config[key] = str(raw).strip()
        else:
            config[key] = str(raw).strip()

    # Checkboxes are absent from the form body when unticked.
    for key, kind, _ in FIELDS:
        if kind == "bool" and key not in form and form.get("_form_submitted"):
            config[key] = False

    if "script_id" in form or "script_ids" in form:
        ids = parse_script_ids(form.get("script_ids") or form.get("script_id"))
        config.pop("script_ids", None)
        config["script_id"] = ids[0] if len(ids) == 1 else ids
        if len(ids) > 1:
            config["script_id"] = ids

    if "hosts" in form:
        config["hosts"] = parse_hosts_map(form["hosts"])
    config.setdefault("hosts", {})

    validate(config)
    return config


def validate(config: dict) -> None:
    """Reject configs ``main.py`` would refuse — before the operator finds out."""
    auth_key = str(config.get("auth_key", ""))
    if auth_key in PLACEHOLDER_AUTH_KEYS:
        raise ConfigError("کلید احراز هویت (auth_key) هنوز مقدار پیش‌فرض است.")
    if len(auth_key) < MIN_AUTH_KEY_LENGTH:
        raise ConfigError(
            f"کلید احراز هویت باید حداقل {MIN_AUTH_KEY_LENGTH} کاراکتر باشد."
        )

    script_id = config.get("script_ids") or config.get("script_id")
    ids = script_id if isinstance(script_id, list) else [script_id]
    if not ids or any((not i) or i in PLACEHOLDER_SCRIPT_IDS for i in ids):
        raise ConfigError("شناسه استقرار Apps Script تنظیم نشده است.")

    listen_port = int(config.get("listen_port", 8085))
    socks_port = int(config.get("socks5_port", 1080))
    if config.get("socks5_enabled", True) and listen_port == socks_port:
        raise ConfigError("پورت HTTP و SOCKS5 نمی‌توانند یکسان باشند.")

    parallel = int(config.get("parallel_relay", 1))
    if parallel > len(ids):
        raise ConfigError(
            "مقدار parallel_relay نمی‌تواند بیشتر از تعداد شناسه‌های استقرار باشد."
        )

    if config.get("lan_sharing") and not (config.get("proxy_auth") or {}).get("enabled"):
        # Not fatal — the upstream tool has always worked this way — but the
        # operator deserves to know the listener will be open to the LAN.
        config.setdefault("_warnings", []).append(
            "اشتراک‌گذاری LAN روشن است ولی احراز هویت کاربران خاموش است؛ "
            "هر دستگاهی در شبکه می‌تواند از پروکسی استفاده کند."
        )


def warnings_of(config: dict) -> list[str]:
    return list(config.get("_warnings") or [])


def strip_internal(config: dict) -> dict:
    """Drop panel-only annotations before writing the file."""
    return {k: v for k, v in config.items() if not k.startswith("_")}
