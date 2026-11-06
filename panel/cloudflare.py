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
import secrets
from datetime import datetime, timedelta, timezone

import requests

from . import paths

log = logging.getLogger("panel.cloudflare")

API_BASE = "https://api.cloudflare.com/client/v4"
GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
TIMEOUT = 30
COMPATIBILITY_DATE = "2024-11-01"

#: Free-plan Workers ceiling. Cloudflare does not report the plan's limit
#: through the API, only the usage, so the limit is carried here and can be
#: overridden for a paid account (where requests are uncapped anyway).
WORKERS_FREE_DAILY_REQUESTS = 100_000

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


def workers_usage(token: str, account_id: str,
                  script_name: str = "") -> dict:
    """Requests this account's Workers have served in the last 24 hours.

    Read from the GraphQL analytics API, which is the only place Cloudflare
    reports it — the REST endpoints expose deployments, not usage. The plan's
    ceiling is not part of the answer, so it is supplied by the caller.

    Raises CloudflareError like the rest of this module; analytics needs its
    own token permission, so a token minted only for deploying will be refused
    here and the caller should treat that as "unknown", not as a failure.
    """
    since = (datetime.now(timezone.utc) - timedelta(hours=24))
    query = """
    query Usage($account: String!, $since: Time!) {
      viewer {
        accounts(filter: {accountTag: $account}) {
          workersInvocationsAdaptive(
            limit: 10000
            filter: {datetime_geq: $since}
          ) {
            sum { requests errors }
            dimensions { scriptName }
          }
        }
      }
    }
    """
    body = {
        "query": query,
        "variables": {
            "account": account_id,
            "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
    try:
        response = requests.post(
            GRAPHQL_URL, headers=_headers(token), json=body, timeout=TIMEOUT,
        )
    except requests.Timeout:
        raise CloudflareError("اتصال به Cloudflare در زمان مقرر پاسخ نداد.")
    except requests.RequestException as exc:
        log.warning("Cloudflare analytics request failed: %s",
                    exc.__class__.__name__)
        raise CloudflareError("اتصال به Cloudflare برقرار نشد.")

    try:
        payload = response.json()
    except ValueError:
        raise CloudflareError(
            f"پاسخ نامعتبر از Cloudflare (کد {response.status_code})."
        )

    # GraphQL reports failures in an `errors` list with HTTP 200, so the
    # status code alone would read as success.
    if payload.get("errors"):
        detail = "; ".join(
            str(e.get("message", "")) for e in payload["errors"]
        ) or "unknown"
        raise CloudflareError(
            f"Cloudflare آمار را نداد — {detail}", payload["errors"],
        )

    accounts = (((payload.get("data") or {}).get("viewer") or {})
                .get("accounts") or [])
    rows = accounts[0].get("workersInvocationsAdaptive", []) if accounts else []

    total = errors = mine = 0
    for row in rows:
        sums = row.get("sum") or {}
        requests_n = int(sums.get("requests") or 0)
        total += requests_n
        errors += int(sums.get("errors") or 0)
        if script_name and (row.get("dimensions") or {}).get(
                "scriptName") == script_name:
            mine += requests_n
    return {
        "requests": total,
        "errors": errors,
        "script_requests": mine if script_name else total,
        "since": since.isoformat(timespec="seconds"),
    }


# ── worker source ─────────────────────────────────────────────────────


def load_worker_source() -> str:
    with open(paths.WORKER_TEMPLATE, encoding="utf-8") as handle:
        return handle.read()


def render_worker(script_name: str, subdomain: str, source: str | None = None,
                  auth_key: str = "") -> str:
    """Point the worker's self-fetch guard at its own real hostname.

    ``worker.js`` ships with ``const WORKER_URL = "myworker.workers.dev";`` and
    uses it to refuse relaying requests aimed back at itself (a loop). Once we
    know the deployed hostname we substitute it in.

    The same pass fills in the Worker's own shared secret
    (``const AUTH_KEY = "__ARAS_AUTH_KEY__";``), so the Worker refuses fetch
    jobs it did not ask for. With no key the placeholder is overwritten with an
    empty string and the Worker stays as unauthenticated as it has always been
    — the relay chain never breaks.
    """
    source = source if source is not None else load_worker_source()
    # json.dumps as the value: a replacement string is not — re.sub would
    # eat the escapes in a key containing backslashes. gasgen.render uses
    # the same lambda-guard for the same reason.
    source = re.sub(
        r'const\s+AUTH_KEY\s*=\s*"[^"]*"\s*;',
        lambda _m: f'const AUTH_KEY = {json.dumps(str(auth_key or ""))};',
        source,
        count=1,
    )
    hostname = f"{script_name}.{subdomain}.workers.dev" if subdomain else ""
    if not hostname:
        return source
    return re.sub(
        r'const\s+WORKER_URL\s*=\s*"[^"]*"\s*;',
        lambda _m: f'const WORKER_URL = "{hostname}";',
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
                  source: str) -> dict:
    """``PUT /accounts/{id}/workers/scripts/{name}`` with an ES-module payload.

    No bindings: the relay Worker reads none. It used to be handed the share
    clients' UUIDs, which stopped meaning anything when the VLESS server moved
    to its own deployment — and until now was still copying those identities
    into a Worker that ignores them.
    """
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": COMPATIBILITY_DATE,
        "bindings": [],
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


def _subdomain_candidates(account_name: str, script_name: str) -> list[str]:
    """Names to try for a new workers.dev subdomain, best first.

    It has to be globally unique across every Cloudflare account, so a single
    guess is not enough. Derived from the account name where there is one, so
    the operator recognises what appeared on their dashboard, with random
    suffixes behind it rather than anything guessable from their identity.
    """
    base = re.sub(r"[^a-z0-9-]+", "-", (account_name or "").lower()).strip("-")
    base = re.sub(r"-{2,}", "-", base)[:40].strip("-")
    seeds = [s for s in (base, script_name) if s]
    out: list[str] = []
    for seed in seeds:
        seed = seed.strip("-")[:50]
        if SCRIPT_NAME_RE.match(seed) and seed not in out:
            out.append(seed)
    for seed in (seeds or ["aras"]):
        for _ in range(4):
            suffix = secrets.token_hex(3)
            candidate = f"{seed.strip('-')[:50]}-{suffix}"
            if SCRIPT_NAME_RE.match(candidate):
                out.append(candidate)
    return out


def create_workers_subdomain(token: str, account_id: str, name: str) -> str:
    """Claim ``name.workers.dev`` for this account. Returns the name taken."""
    payload = _call(
        "PUT", f"/accounts/{account_id}/workers/subdomain", token,
        json={"subdomain": name},
    )
    got = (payload.get("result") or {}).get("subdomain") or name
    log.info("Created workers.dev subdomain '%s'", got)
    return got


def ensure_workers_subdomain(token: str, account_id: str,
                             script_name: str = "aras") -> tuple[str, bool]:
    """The account's workers.dev subdomain, creating one if it has none.

    Cloudflare only creates it when the dashboard's Workers page is opened, so
    an account that has never been there fails a deploy with error 10007 and a
    link to go and click. Doing it over the API removes that detour.

    Returns ``(subdomain, created)`` so the caller can tell the operator when a
    public name was claimed on their behalf — it is account-wide and shows on
    their dashboard, so it should never appear silently.
    """
    try:
        existing = get_workers_subdomain(token, account_id)
        if existing:
            return existing, False
    except CloudflareError as exc:
        # 10007 is "no subdomain yet", which is the case this exists to fix.
        # Anything else — a bad token, no permission — must not be papered over
        # by trying to create one.
        if not _is_missing_subdomain(exc):
            raise

    account_name = ""
    try:
        for acct in list_accounts(token):
            if acct.get("id") == account_id:
                account_name = acct.get("name") or ""
                break
    except CloudflareError:
        # Listing needs a permission the token may not have; the fallback
        # candidates do not depend on it.
        pass

    last: CloudflareError | None = None
    for candidate in _subdomain_candidates(account_name, script_name):
        try:
            return create_workers_subdomain(token, account_id, candidate), True
        except CloudflareError as exc:
            if not _is_subdomain_taken(exc):
                raise
            last = exc
            log.info("workers.dev name '%s' is taken, trying another", candidate)
    raise CloudflareError(
        "نتوانستم زیردامنه workers.dev بسازم — همه‌ی نام‌های پیشنهادی گرفته "
        "شده‌اند. یک بار از داشبورد Cloudflare بخش Workers را باز کنید تا "
        "خودش بسازد، سپس دوباره تلاش کنید.",
        getattr(last, "errors", None),
    )


def _error_codes(exc: CloudflareError) -> set[int]:
    codes = set()
    for item in getattr(exc, "errors", None) or []:
        try:
            codes.add(int(item.get("code")))
        except (TypeError, ValueError):
            continue
    return codes


def _is_missing_subdomain(exc: CloudflareError) -> bool:
    if 10007 in _error_codes(exc):
        return True
    return "workers.dev subdomain" in str(exc).lower()


def _is_subdomain_taken(exc: CloudflareError) -> bool:
    text = str(exc).lower()
    return (10036 in _error_codes(exc)
            or "already" in text or "taken" in text or "unavailable" in text)


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
        raise CloudflareError("Account ID باید یک رشته ۳۲ کاراکتری هگز باشد.",
                              errors=[{"manual": True}])

    # Listing accounts needs "Account Settings: Read", which a token made only
    # for Workers does not carry — and such a token deploys perfectly well.
    # Failing here would strand exactly the people whose setup already worked,
    # so a lookup we cannot perform falls back to asking, never to a dead end.
    manual_hint = (
        "Account ID را خودکار پیدا نکردم، چون این توکن دسترسی "
        "«Account Settings: Read» ندارد. یا Account ID را در همین کادر وارد "
        "کنید (از داشبورد کلودفلر، بخش Workers، ستون سمت راست)، یا توکن را با "
        "آن دسترسی دوباره بسازید."
    )
    try:
        accounts = list_accounts(token)
    except CloudflareError as exc:
        log.info("Account lookup refused (%s) — asking for the ID instead",
                 exc.message)
        raise CloudflareError(manual_hint, errors=[{"manual": True}]) from exc

    if not accounts:
        raise CloudflareError(manual_hint, errors=[{"manual": True}])
    if len(accounts) == 1:
        log.info("Account ID resolved automatically: %s", accounts[0]["name"])
        return accounts[0]["id"]

    names = "، ".join(a["name"] for a in accounts[:5])
    raise CloudflareError(
        f"این توکن به {len(accounts)} حساب دسترسی دارد ({names}). "
        "یکی را انتخاب کنید.",
        errors=[{"accounts": accounts}],
    )


def deploy(token: str, account_id: str, script_name: str,
           auth_key: str = "",
) -> dict:
    """Full deploy. Returns the public worker URL and the steps that ran."""
    script_name = validate_script_name(script_name)

    steps: list[dict] = []

    def record(label: str, ok: bool, detail: str = ""):
        steps.append({"label": label, "ok": ok, "detail": detail})

    # The token is checked before anything is inferred from it. Resolving the
    # account first meant a simply invalid token came back as "your token is
    # missing Account Settings: Read", which sends the reader off to fix a
    # permission on a token that was never going to work.
    token_info = verify_token(token)
    record("بررسی توکن", True, token_info.get("status", ""))

    account_id = resolve_account_id(token, account_id)
    record("یافتن حساب", True, account_id[:8] + "…")

    subdomain, created = ensure_workers_subdomain(token, account_id, script_name)
    record(
        "ساخت زیردامنه" if created else "یافتن زیردامنه", True,
        f"{subdomain}.workers.dev" + (" (تازه ساخته شد)" if created else ""),
    )

    source = render_worker(script_name, subdomain, auth_key=auth_key)
    upload_script(token, account_id, script_name, source)
    detail = f"{len(source)} بایت"
    record("آپلود اسکریپت", True, detail)

    enable_workers_dev(token, account_id, script_name)
    record("فعال‌سازی workers.dev", True, "")

    worker_url = f"https://{script_name}.{subdomain}.workers.dev"
    return {
        "worker_url": worker_url,
        "subdomain": subdomain,
        "script_name": script_name,
        # The caller stores this: it was persisting whatever the form sent,
        # which is now empty, so a successful deploy used to forget the account.
        "account_id": account_id,
        "steps": steps,
    }
