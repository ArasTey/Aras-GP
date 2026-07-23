"""Cloudflare Workers deployment.

This is the one part of the deploy story that is genuinely automatable, so it
is automated end to end: verify the token, discover the account's workers.dev
subdomain, upload ``deploy/cloudflare-worker/worker.js`` as an ES module, and
switch the workers.dev route on.

**Every request in this module goes to ``api.cloudflare.com`` and nowhere else.**
The panel has no other outbound destination — there is no telemetry, no license
server, no update check. That is a deliberate property of a censorship-
circumvention tool: a central endpoint the panel phones home to would be exactly
the surveillance chokepoint this project exists to avoid.

The API token is never written to a log. It is only persisted if the operator
explicitly ticks "remember token", and then only into a ``0600`` file.
"""

from __future__ import annotations

import json
import logging
import re

import requests

from . import paths

log = logging.getLogger("panel.cloudflare")

API_BASE = "https://api.cloudflare.com/client/v4"
TIMEOUT = 30
COMPATIBILITY_DATE = "2024-11-01"

SCRIPT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")

#: Deep link that opens Cloudflare's token screen with exactly the permissions
#: this panel needs already ticked, so the operator only has to confirm.
#:   workers_scripts:edit   → upload the script, enable workers.dev
#:   account_settings:read  → list accounts so Account ID can be auto-filled
TOKEN_TEMPLATE_URL = (
    "https://dash.cloudflare.com/profile/api-tokens"
    "?permissionGroupKeys=%5B%7B%22key%22%3A%22workers_scripts%22%2C%22type%22"
    "%3A%22edit%22%7D%2C%7B%22key%22%3A%22account_settings%22%2C%22type%22%3A"
    "%22read%22%7D%5D&name=Aras-GP+Panel&accountId=%2A&zoneId=all"
)


class CloudflareError(RuntimeError):
    """Carries a Persian message plus the raw API errors for the details pane."""

    def __init__(self, message: str, errors: list | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Aras-GP-Panel",
    }


def _call(method: str, path: str, token: str, **kwargs) -> dict:
    url = f"{API_BASE}{path}"
    try:
        response = requests.request(
            method, url, headers=_headers(token), timeout=TIMEOUT, **kwargs
        )
    except requests.Timeout:
        raise CloudflareError("اتصال به Cloudflare در زمان مقرر پاسخ نداد.")
    except requests.RequestException as exc:
        # Log the failure without the URL's credentials or the token header.
        log.warning("Cloudflare request failed (%s %s): %s", method, path, exc.__class__.__name__)
        raise CloudflareError("اتصال به Cloudflare برقرار نشد. اینترنت یا فیلترینگ را بررسی کنید.")

    try:
        payload = response.json()
    except ValueError:
        raise CloudflareError(
            f"پاسخ نامعتبر از Cloudflare (کد {response.status_code})."
        )

    if not payload.get("success", False):
        errors = payload.get("errors") or []
        detail = "; ".join(
            f"{e.get('code', '')}: {e.get('message', '')}".strip(": ")
            for e in errors
        ) or f"HTTP {response.status_code}"
        raise CloudflareError(f"Cloudflare درخواست را رد کرد — {detail}", errors)

    return payload


# ── read-only helpers ─────────────────────────────────────────────────


def verify_token(token: str) -> dict:
    """Confirm the token works and report its status."""
    payload = _call("GET", "/user/tokens/verify", token)
    return payload.get("result") or {}


def list_accounts(token: str) -> list[dict]:
    """Accounts the token can see — saves the operator hunting for the ID."""
    payload = _call("GET", "/accounts?per_page=50", token)
    return [
        {"id": item.get("id"), "name": item.get("name")}
        for item in (payload.get("result") or [])
    ]


def get_workers_subdomain(token: str, account_id: str) -> str:
    payload = _call("GET", f"/accounts/{account_id}/workers/subdomain", token)
    return (payload.get("result") or {}).get("subdomain") or ""


def list_scripts(token: str, account_id: str) -> list[dict]:
    payload = _call("GET", f"/accounts/{account_id}/workers/scripts", token)
    return [
        {"id": item.get("id"), "modified_on": item.get("modified_on")}
        for item in (payload.get("result") or [])
    ]


# ── worker source ─────────────────────────────────────────────────────


def load_worker_source() -> str:
    with open(paths.WORKER_TEMPLATE, encoding="utf-8") as handle:
        return handle.read()


def render_worker(script_name: str, subdomain: str, source: str | None = None) -> str:
    """Point the worker's self-fetch guard at its own real hostname.

    ``worker.js`` ships with ``const WORKER_URL = "myworker.workers.dev";`` and
    uses it to refuse relaying requests aimed back at itself (a loop). Once we
    know the deployed hostname we substitute it in.
    """
    source = source if source is not None else load_worker_source()
    hostname = f"{script_name}.{subdomain}.workers.dev" if subdomain else ""
    if not hostname:
        return source
    return re.sub(
        r'const\s+WORKER_URL\s*=\s*"[^"]*"\s*;',
        f'const WORKER_URL = "{hostname}";',
        source,
        count=1,
    )


# ── deploy ────────────────────────────────────────────────────────────


def validate_script_name(name: str) -> str:
    name = (name or "").strip().lower()
    if not SCRIPT_NAME_RE.match(name):
        raise CloudflareError(
            "نام Worker باید فقط شامل حروف کوچک، عدد و خط تیره باشد "
            "(و با حرف یا عدد شروع و تمام شود)."
        )
    return name


def upload_script(token: str, account_id: str, script_name: str,
                  source: str, vless_uuids: list[str] | None = None) -> dict:
    """``PUT /accounts/{id}/workers/scripts/{name}`` with an ES-module payload.

    ``vless_uuids`` are bound as ``VLESS_UUIDS`` so the Worker's VLESS server
    accepts exactly the panel's friends and no one else. With none bound the
    Worker refuses every VLESS client — it never becomes an open proxy.
    """
    bindings = []
    if vless_uuids:
        bindings.append({
            "type": "plain_text",
            "name": "VLESS_UUIDS",
            "text": json.dumps(list(vless_uuids)),
        })
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": COMPATIBILITY_DATE,
        "bindings": bindings,
    }

    files = {
        "metadata": (None, json.dumps(metadata), "application/json"),
        "worker.js": ("worker.js", source, "application/javascript+module"),
    }

    payload = _call(
        "PUT", f"/accounts/{account_id}/workers/scripts/{script_name}",
        token, files=files,
    )
    result = payload.get("result") or {}
    log.info("Worker '%s' uploaded (%d bytes of source)", script_name, len(source))
    return result


def enable_workers_dev(token: str, account_id: str, script_name: str) -> bool:
    """Publish the script on ``*.workers.dev`` so the GAS relay can reach it."""
    payload = _call(
        "POST", f"/accounts/{account_id}/workers/scripts/{script_name}/subdomain",
        token, json={"enabled": True},
    )
    return bool((payload.get("result") or {}).get("enabled", True))


def resolve_account_id(token: str, account_id: str = "") -> str:
    """Return the account to deploy into, asking Cloudflare when not told.

    The ID is not something an operator should have to go and find: the token
    already implies which accounts it can touch. When it selects exactly one —
    the ordinary case — that is the answer. Only a token spanning several
    accounts needs a decision, and then the caller is told which ones so it can
    ask rather than guess.
    """
    account_id = (account_id or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", account_id):
        return account_id
    if account_id:
        raise CloudflareError("Account ID باید یک رشته ۳۲ کاراکتری هگز باشد.")

    accounts = list_accounts(token)
    if not accounts:
        raise CloudflareError(
            "این توکن به هیچ حسابی دسترسی ندارد. موقع ساخت توکن، دسترسی "
            "«Account Settings: Read» را هم بدهید."
        )
    if len(accounts) == 1:
        log.info("Account ID resolved automatically: %s", accounts[0]["name"])
        return accounts[0]["id"]

    names = "، ".join(a["name"] for a in accounts[:5])
    raise CloudflareError(
        f"این توکن به {len(accounts)} حساب دسترسی دارد ({names}). "
        "یکی را از فهرست انتخاب کنید.",
        errors=[{"accounts": accounts}],
    )


def deploy(token: str, account_id: str, script_name: str,
           vless_uuids: list[str] | None = None) -> dict:
    """Full deploy. Returns the public worker URL and the steps that ran."""
    account_id = resolve_account_id(token, account_id)
    script_name = validate_script_name(script_name)

    steps: list[dict] = []

    def record(label: str, ok: bool, detail: str = ""):
        steps.append({"label": label, "ok": ok, "detail": detail})

    token_info = verify_token(token)
    record("بررسی توکن", True, token_info.get("status", ""))

    subdomain = get_workers_subdomain(token, account_id)
    if not subdomain:
        raise CloudflareError(
            "این حساب هنوز زیردامنه workers.dev ندارد. یک بار از داشبورد "
            "Cloudflare بخش Workers را فعال کنید و دوباره تلاش کنید."
        )
    record("یافتن زیردامنه", True, f"{subdomain}.workers.dev")

    source = render_worker(script_name, subdomain)
    upload_script(token, account_id, script_name, source, vless_uuids)
    detail = f"{len(source)} بایت"
    if vless_uuids:
        detail += f" + {len(vless_uuids)} کلاینت VLESS"
    record("آپلود اسکریپت", True, detail)

    enable_workers_dev(token, account_id, script_name)
    record("فعال‌سازی workers.dev", True, "")

    worker_url = f"https://{script_name}.{subdomain}.workers.dev"
    return {
        "worker_url": worker_url,
        "subdomain": subdomain,
        "script_name": script_name,
        "steps": steps,
    }
