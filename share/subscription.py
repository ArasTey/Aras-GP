"""Subscription building: many addresses, one link.

A client's config names one address. If that edge stops answering — and which
Cloudflare edges answer differs by network and changes over time — the config
is dead until someone edits it by hand.

A subscription is a list, so the fix is to put every address in it. Phone apps
read all of them, and their own "test and pick the fastest" behaviour handles
the rest: one entry per address per client, each labelled with the address so
the user can see which one their app settled on.

This module only assembles text. It does not deploy, it does not talk to
Cloudflare, and it does not touch the relay's config.
"""

from __future__ import annotations

import base64
import ipaddress
import re
from urllib.parse import quote

#: What a phone app negotiates. WebSocket is HTTP/1.1, so that is the default.
DEFAULT_ALPN = "http/1.1"
DEFAULT_FINGERPRINT = "chrome"


def normalize_address(value) -> str:
    """An IP literal or hostname to dial, or "" when it is not usable.

    Cloudflare routes on SNI and Host rather than on which edge the connection
    reached, so this can be any reachable edge while the config keeps naming
    the Worker. Refused rather than corrected when malformed — a quietly
    dropped address looks like it was accepted.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^[a-zA-Z][\w+.-]*://", "", text).split("/")[0].strip()
    if not text:
        return ""
    if text.startswith("[") and text.endswith("]"):
        try:
            ipaddress.IPv6Address(text[1:-1])
            return text
        except ValueError:
            return ""
    try:
        ipaddress.ip_address(text)
        return text
    except ValueError:
        pass
    if len(text) <= 253 and re.fullmatch(
            r"(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*",
            text):
        return text.lower()
    return ""


def parse_addresses(raw) -> list[str]:
    """Split an operator's paste into addresses, keeping the order given.

    Accepts newlines, commas or spaces, because a list of IPs gets pasted from
    wherever it was found. Duplicates are dropped so a repeated address does
    not appear twice in every client's app.
    """
    if isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        items = re.split(r"[\s,;]+", str(raw or ""))
    out: list[str] = []
    for item in items:
        addr = normalize_address(item)
        if addr and addr not in out:
            out.append(addr)
    return out


def vless_link(uuid: str, host: str, path: str, address: str = "",
               label: str = "", alpn: str = DEFAULT_ALPN,
               fingerprint: str = DEFAULT_FINGERPRINT) -> str:
    """One ``vless://`` config.

    ``host`` is the Worker's hostname and stays in ``sni`` and ``host``, which
    is what terminates the TLS and what Cloudflare routes on. ``address`` is
    only what the client dials; empty means dial the Worker's name.
    """
    if not uuid or not host:
        return ""
    dial = normalize_address(address) or host
    query = (
        "encryption=none"
        "&security=tls"
        "&sni=" + quote(host) +
        "&type=ws"
        "&host=" + quote(host) +
        "&path=" + quote(path or "/", safe="") +
        "&alpn=" + quote(alpn, safe="") +
        "&fp=" + quote(fingerprint)
    )
    tag = quote(label or "aras", safe="")
    return f"vless://{uuid}@{dial}:443?{query}#{tag}"


def build_links(clients: list[dict], host: str, path: str,
                addresses: list[str] | None = None,
                alpn: str = DEFAULT_ALPN,
                fingerprint: str = DEFAULT_FINGERPRINT) -> list[str]:
    """Every config: one per client per address.

    With no addresses this is one entry per client dialling the Worker's own
    name, which is the plain case. With addresses it is the cross product, and
    each entry is labelled with the address it dials so a user can tell which
    one their app chose.
    """
    addrs = list(addresses or [])
    out: list[str] = []
    for client in clients:
        uuid = client.get("uuid")
        if not uuid or not client.get("enabled", True):
            continue
        name = client.get("name") or "aras"
        if not addrs:
            link = vless_link(uuid, host, path, label=name,
                              alpn=alpn, fingerprint=fingerprint)
            if link:
                out.append(link)
            continue
        for addr in addrs:
            link = vless_link(uuid, host, path, address=addr,
                              label=f"{name} · {addr}",
                              alpn=alpn, fingerprint=fingerprint)
            if link:
                out.append(link)
    return out


def encode(links: list[str]) -> str:
    """The base64 blob a phone app expects behind a subscription URL."""
    if not links:
        return ""
    return base64.b64encode("\n".join(links).encode("utf-8")).decode("ascii")
