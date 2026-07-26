"""Deploying the share Worker.

Separate from ``panel.cloudflare`` on purpose. That module owns the relay's
Worker; this one owns a different script, under a different name, and the two
must never write to each other's deployment. A bug here should be able to cost
the share feature and nothing else — the relay is what the operator actually
depends on.

The only thing borrowed from the panel is the transport: the same API base, the
same error type, the same "never log the token" discipline. Reimplementing that
would be a second place to get authentication wrong.
"""

from __future__ import annotations

import json
import logging
import os

import requests

from panel.cloudflare import (
    API_BASE, CloudflareError, TIMEOUT, _headers, ensure_workers_subdomain,
)
from . import identity, subscription

log = logging.getLogger("share.worker")

COMPATIBILITY_DATE = "2024-11-01"

WORKER_SOURCE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "deploy", "share-worker", "worker.js",
)


def load_source() -> str:
    with open(WORKER_SOURCE, encoding="utf-8") as handle:
        return handle.read()


def _call(method: str, path: str, token: str, **kwargs) -> dict:
    """Same contract as the panel's ``_call``, kept local to this module.

    Importing the panel's private helper would tie the share deploy to changes
    made for the relay's, which is the coupling this module exists to avoid.
    """
    try:
        response = requests.request(
            method, f"{API_BASE}{path}", headers=_headers(token),
            timeout=TIMEOUT, **kwargs,
        )
    except requests.Timeout:
        raise CloudflareError("اتصال به Cloudflare در زمان مقرر پاسخ نداد.")
    except requests.RequestException as exc:
        log.warning("Share deploy request failed (%s %s): %s",
                    method, path, exc.__class__.__name__)
        raise CloudflareError("اتصال به Cloudflare برقرار نشد.")

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
        raise CloudflareError(f"Cloudflare درخواست را رد کرد — {detail}",
                              errors)
    return payload


def upload(token: str, account_id: str, script_name: str, source: str,
           bindings: dict) -> dict:
    """Upload the script with its plain-text bindings.

    Bindings rather than substitution into the source: a value edited into the
    script would be visible to anyone who fetched it, and changing one would
    mean regenerating and re-uploading the whole file.
    """
    metadata = {
        "main_module": "worker.js",
        "compatibility_date": COMPATIBILITY_DATE,
        "bindings": [
            {"type": "plain_text", "name": name, "text": str(value)}
            for name, value in bindings.items()
        ],
    }
    files = {
        "metadata": (None, json.dumps(metadata), "application/json"),
        "worker.js": ("worker.js", source, "application/javascript+module"),
    }
    payload = _call(
        "PUT", f"/accounts/{account_id}/workers/scripts/{script_name}",
        token, files=files,
    )
    log.info("Share worker '%s' uploaded (%d bytes)", script_name, len(source))
    return payload.get("result") or {}


def enable_workers_dev(token: str, account_id: str, script_name: str) -> bool:
    payload = _call(
        "POST",
        f"/accounts/{account_id}/workers/scripts/{script_name}/subdomain",
        token, json={"enabled": True},
    )
    return bool((payload.get("result") or {}).get("enabled", True))


def delete(token: str, account_id: str, script_name: str) -> None:
    """Remove the deployment. Already absent counts as success.

    Matched on the message rather than an error code: the code that used to be
    checked here was 10007, which is Cloudflare's "this account has no
    workers.dev subdomain" — copied from the function that handles that, and
    wrong for this one. A substring search for a number over the whole message
    would also match a script whose name happened to contain it.

    Anything other than a missing script is re-raised. Reporting a failed
    delete as success would leave a live Worker the panel believes is gone.
    """
    try:
        _call("DELETE",
              f"/accounts/{account_id}/workers/scripts/{script_name}",
              token)
    except CloudflareError as exc:
        text = str(exc).lower()
        if "not found" in text or "could not find" in text \
                or "does not exist" in text:
            log.info("Share worker '%s' was already gone", script_name)
            return
        raise


def deploy(token: str, account_id: str, clients: list[dict],
           addresses: list[str] | None = None,
           script_name: str = "", ws_path: str = "", sub_path: str = "",
           alpn: str = subscription.DEFAULT_ALPN,
           fingerprint: str = subscription.DEFAULT_FINGERPRINT) -> dict:
    """Deploy a share Worker and return everything needed to reach it.

    Names and paths are generated when not supplied, so a first deploy needs no
    decisions from the operator and two operators never land on the same ones.
    Redeploying with the existing values keeps every config that is already in
    someone's app working.

    The subscription is built here and shipped as a binding, so the Worker can
    serve it without the panel being reachable — which is the point: a friend
    on another network cannot fetch a subscription from a panel bound to
    localhost.
    """
    script_name = script_name or identity.random_script_name()
    if not identity.valid_script_name(script_name):
        raise CloudflareError("نام Worker نامعتبر است.")
    ws_path = identity.normalize_path(ws_path, identity.random_path())
    sub_path = identity.normalize_path(sub_path, identity.random_path(1))
    if ws_path == sub_path:
        # Same path for both would make the subscription reachable by anyone
        # who found the WebSocket endpoint, and vice versa.
        sub_path = identity.random_path(1)

    subdomain, created = ensure_workers_subdomain(token, account_id,
                                                  script_name)
    host = f"{script_name}.{subdomain}.workers.dev"

    uuids = [c["uuid"] for c in clients
             if c.get("uuid") and c.get("enabled", True)]
    links = subscription.build_links(
        clients, host, ws_path, addresses=addresses,
        alpn=alpn, fingerprint=fingerprint,
    )
    bindings = {
        "VLESS_UUIDS": json.dumps(uuids),
        "WS_PATH": ws_path,
        "SUB_PATH": sub_path,
        "SUB_BODY": subscription.encode(links),
    }

    upload(token, account_id, script_name, load_source(), bindings)
    try:
        enable_workers_dev(token, account_id, script_name)
    except CloudflareError as exc:
        # The script is on the account by this point. Letting the failure
        # propagate bare meant the caller never learned the generated name, so
        # it was not recorded — and the next attempt generated another random
        # name and left this one behind. Carry the name out so it can be saved
        # and reused instead of accumulating orphans.
        exc.script_name = script_name
        raise

    return {
        "script_name": script_name,
        "subdomain": subdomain,
        "subdomain_created": created,
        "host": host,
        "ws_path": ws_path,
        "sub_path": sub_path,
        "sub_url": f"https://{host}{sub_path}",
        "addresses": list(addresses or []),
        "clients": len(uuids),
        "links": len(links),
    }
