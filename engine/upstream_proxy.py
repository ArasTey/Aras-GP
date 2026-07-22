"""Outbound SOCKS5 client — send selected hosts through the operator's own VPS.

Why this exists
---------------
Traffic that leaves through Cloudflare Workers arrives at the destination from
Cloudflare's egress ranges. A growing number of services refuse those ranges
outright; OpenAI is the usual example, and the failure looks like Cloudflare's
own "Unable to load site" interstitial rather than anything the relay can fix.

The fix is not a workaround inside the relay — it is a different exit. When the
operator runs the bundled installer on any cheap VPS they get a SOCKS5 endpoint
with a stable, residential-looking-enough IP that they control. Hosts listed in
``upstream_proxy.hosts`` are dialled through that endpoint instead of the
Apps Script chain, which also removes two network hops for those domains.

Everything else keeps using the relay. This is a targeted exit, not a VPN.

The implementation is a minimal RFC 1928 / RFC 1929 client: enough to CONNECT
and hand back a raw stream pair, with no third-party dependency.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import struct
from urllib.parse import unquote, urlparse

log = logging.getLogger("Upstream")

CONNECT_TIMEOUT = 12.0
HANDSHAKE_TIMEOUT = 10.0

_REPLY_ERRORS = {
    0x01: "general SOCKS server failure",
    0x02: "connection not allowed by ruleset",
    0x03: "network unreachable",
    0x04: "host unreachable",
    0x05: "connection refused",
    0x06: "TTL expired",
    0x07: "command not supported",
    0x08: "address type not supported",
}


class UpstreamError(RuntimeError):
    """Raised when the upstream proxy refuses or cannot be reached."""


class UpstreamProxy:
    """A parsed ``socks5://user:pass@host:port`` endpoint.

    Instances are cheap and immutable; the object holds no sockets and no
    background state, so a config reload just builds a new one.
    """

    __slots__ = ("host", "port", "username", "password", "raw")

    def __init__(self, url: str):
        parsed = urlparse((url or "").strip())
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("socks5", "socks5h", ""):
            raise ValueError(
                "آدرس پروکسی بالادست باید با socks5:// شروع شود."
            )
        if not parsed.hostname:
            raise ValueError("آدرس پروکسی بالادست میزبان ندارد.")

        self.host = parsed.hostname
        self.port = int(parsed.port or 1080)
        # Credentials may legitimately contain % - encoded characters.
        self.username = unquote(parsed.username) if parsed.username else ""
        self.password = unquote(parsed.password) if parsed.password else ""
        self.raw = url.strip()

    def __repr__(self) -> str:      # never leak the password into a log line
        auth = f"{self.username}:***@" if self.username else ""
        return f"socks5://{auth}{self.host}:{self.port}"

    @property
    def safe_url(self) -> str:
        return repr(self)

    # ── protocol ──────────────────────────────────────────────────────

    async def connect(self, dest_host: str, dest_port: int):
        """CONNECT through the proxy. Returns ``(reader, writer)``.

        The destination name is sent as a domain, not resolved locally, so DNS
        happens at the VPS. That matters here: resolving locally would leak the
        lookup to the very network the operator is trying to get around.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise UpstreamError(f"cannot reach upstream {self!r}: {exc}") from exc

        try:
            await asyncio.wait_for(
                self._handshake(reader, writer, dest_host, dest_port),
                timeout=HANDSHAKE_TIMEOUT,
            )
        except BaseException:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            raise
        return reader, writer

    async def _handshake(self, reader, writer, dest_host: str, dest_port: int):
        methods = b"\x02\x00\x02" if self.username else b"\x01\x00"
        writer.write(b"\x05" + methods)
        await writer.drain()

        head = await reader.readexactly(2)
        if head[0] != 0x05:
            raise UpstreamError("upstream is not a SOCKS5 proxy")

        method = head[1]
        if method == 0xFF:
            raise UpstreamError("upstream rejected our authentication methods")
        if method == 0x02:
            if not self.username:
                raise UpstreamError("upstream wants a username but none is set")
            await self._authenticate(reader, writer)
        elif method != 0x00:
            raise UpstreamError(f"unsupported SOCKS5 auth method {method:#x}")

        writer.write(b"\x05\x01\x00" + self._address(dest_host) +
                     struct.pack("!H", dest_port))
        await writer.drain()

        reply = await reader.readexactly(4)
        if reply[0] != 0x05:
            raise UpstreamError("malformed SOCKS5 reply")
        if reply[1] != 0x00:
            raise UpstreamError(
                _REPLY_ERRORS.get(reply[1], f"SOCKS5 error {reply[1]:#x}")
            )

        # Drain the bound address so the stream starts at the payload.
        atyp = reply[3]
        if atyp == 0x01:
            await reader.readexactly(4)
        elif atyp == 0x03:
            length = (await reader.readexactly(1))[0]
            await reader.readexactly(length)
        elif atyp == 0x04:
            await reader.readexactly(16)
        else:
            raise UpstreamError("upstream returned an unknown address type")
        await reader.readexactly(2)

    async def _authenticate(self, reader, writer):
        user = self.username.encode("utf-8")
        password = self.password.encode("utf-8")
        if len(user) > 255 or len(password) > 255:
            raise UpstreamError("upstream credentials are too long")
        writer.write(bytes([0x01, len(user)]) + user +
                     bytes([len(password)]) + password)
        await writer.drain()
        result = await reader.readexactly(2)
        if result[1] != 0x00:
            raise UpstreamError("upstream rejected the username or password")

    @staticmethod
    def _address(host: str) -> bytes:
        """Encode the destination — literal IPs go as IPs, names stay names."""
        try:
            ip = ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            encoded = host.encode("idna") if host.isascii() is False else host.encode()
            if len(encoded) > 255:
                raise UpstreamError("destination hostname is too long")
            return bytes([0x03, len(encoded)]) + encoded
        if ip.version == 4:
            return b"\x01" + socket.inet_aton(str(ip))
        return b"\x04" + socket.inet_pton(socket.AF_INET6, str(ip))


# ── host matching ─────────────────────────────────────────────────────

#: Domains that routinely refuse Cloudflare Workers egress. Used as the
#: default list so the feature is useful the moment it is switched on; the
#: operator can replace it entirely from the panel.
DEFAULT_AI_HOSTS = (
    "openai.com",
    "chatgpt.com",
    "oaistatic.com",
    "oaiusercontent.com",
    "claude.ai",
    "anthropic.com",
    "gemini.google.com",
    "perplexity.ai",
    "x.ai",
    "grok.com",
    "cdn.usefathom.com",
)


class HostMatcher:
    """Exact + suffix matcher, mirroring how the engine treats host rules.

    ``example.com`` matches the domain and everything under it, so the operator
    does not have to enumerate subdomains for a service that has dozens.
    """

    __slots__ = ("_exact", "_suffixes")

    def __init__(self, hosts):
        exact, suffixes = set(), []
        for raw in hosts or ():
            item = str(raw).strip().lower().rstrip(".")
            if not item:
                continue
            if item.startswith("."):
                suffixes.append(item)
            else:
                exact.add(item)
                suffixes.append("." + item)
        self._exact = exact
        self._suffixes = tuple(suffixes)

    def __bool__(self) -> bool:
        return bool(self._exact or self._suffixes)

    def matches(self, host: str) -> bool:
        if not host:
            return False
        item = host.strip().lower().rstrip(".")
        if item in self._exact:
            return True
        return item.endswith(self._suffixes) if self._suffixes else False
