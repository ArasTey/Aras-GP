"""Two-tier response cache: LRU in memory, persistent on disk.

Every cache miss costs a full Apps Script round trip — roughly two seconds
of the operator's daily quota. The old cache lived only in RAM, so closing
the relay threw away everything it had learned, and the next session paid
for the same fonts, stylesheets and images all over again.

Layout
------
``memory``  bounded LRU, answers in microseconds, holds the hot set.
``disk``    one file per entry under the OS cache directory, survives
            restarts and reboots. Read and written on a worker thread so a
            slow disk never stalls the event loop.

A disk hit is promoted into memory, so a page's second visit is served from
RAM. Nothing here is on the fast path for a miss: lookups that fail cost one
dict probe and one ``os.path.exists``.

The on-disk format is deliberately dumb — an 8-byte expiry, a length-prefixed
URL for collision checking, then the raw HTTP response. No pickle, because a
cache directory is user-writable and unpickling it would be a code-execution
hole in a security tool.
"""

from __future__ import annotations

import asyncio
import collections
import hashlib
import logging
import os
import platform
import re
import struct
import time

from constants import (
    CACHE_TTL_MAX,
    CACHE_TTL_STATIC_LONG,
    CACHE_TTL_STATIC_MED,
    STATIC_EXTS,
)

log = logging.getLogger("Cache")

_MAGIC = b"AGP1"
_HEADER = struct.Struct("<4sdI")   # magic, expires_at, url length


def default_cache_dir() -> str:
    """The place this platform expects a cache to live.

    A cache belongs in the OS cache location, not the repo: it is disposable,
    it should not be backed up, and on macOS it is what the system purges
    first when the disk fills.
    """
    system = platform.system()
    if system == "Darwin":
        base = os.path.expanduser("~/Library/Caches")
    elif system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = (os.environ.get("XDG_CACHE_HOME")
                or os.path.expanduser("~/.cache"))
    return os.path.join(base, "Aras-GP", "responses")


#: Headers that must not be replayed from a cached copy. Set-Cookie is the one
#: that matters: serving a stored cookie to a later client would hand them
#: someone else's, and re-issuing a stale one is wrong even for a single user.
_STRIP_ON_STORE = (b"set-cookie", b"set-cookie2")


def strip_uncacheable_headers(raw_response: bytes) -> bytes:
    """Remove per-client headers so a response is safe to store and replay."""
    split = raw_response.find(b"\r\n\r\n")
    if split < 0:
        return raw_response
    head, body = raw_response[:split], raw_response[split:]
    lines = head.split(b"\r\n")
    kept = [lines[0]]
    for line in lines[1:]:
        name = line.split(b":", 1)[0].strip().lower()
        if name in _STRIP_ON_STORE:
            continue
        kept.append(line)
    return b"\r\n".join(kept) + body


class ResponseCache:
    """Bounded LRU over raw HTTP responses, optionally backed by disk."""

    def __init__(self, max_mb: int = 50, disk_mb: int = 512,
                 disk_dir: str | None = None, disk_enabled: bool = True):
        self._store: collections.OrderedDict[str, tuple[bytes, float]] = (
            collections.OrderedDict()
        )
        self._size = 0
        self._max = max(1, max_mb) * 1024 * 1024
        self.hits = 0
        self.misses = 0
        self.disk_hits = 0

        self._disk_dir = disk_dir or default_cache_dir()
        self._disk_max = max(0, disk_mb) * 1024 * 1024
        self.disk_enabled = bool(disk_enabled) and self._disk_max > 0
        self._disk_size = 0
        self._pending: set[str] = set()

        if self.disk_enabled:
            try:
                os.makedirs(self._disk_dir, exist_ok=True)
                self._disk_size = self._measure_disk()
                log.info("Disk cache: %s (%.0f MB used of %d MB)",
                         self._disk_dir, self._disk_size / 1e6, disk_mb)
            except OSError as exc:
                log.warning("Disk cache disabled (%s): %s", self._disk_dir, exc)
                self.disk_enabled = False

    # ── memory tier ───────────────────────────────────────────────────

    def get(self, url: str) -> bytes | None:
        entry = self._store.get(url)
        if not entry:
            self.misses += 1
            return None
        raw, expires = entry
        if time.time() > expires:
            self._size -= len(raw)
            del self._store[url]
            self.misses += 1
            return None
        # Touch: this is what makes the eviction below LRU rather than FIFO,
        # which used to throw away the very entries a page reloads most.
        self._store.move_to_end(url)
        self.hits += 1
        return raw

    def put(self, url: str, raw_response: bytes, ttl: int = 300):
        size = len(raw_response)
        if size > self._max // 4 or size == 0:
            return
        while self._size + size > self._max and self._store:
            _, (evicted, _) = self._store.popitem(last=False)
            self._size -= len(evicted)
        if url in self._store:
            self._size -= len(self._store[url][0])
        self._store[url] = (raw_response, time.time() + ttl)
        self._store.move_to_end(url)
        self._size += size

    # ── disk tier ─────────────────────────────────────────────────────

    def _path_for(self, url: str) -> str:
        digest = hashlib.sha256(url.encode("utf-8", "replace")).hexdigest()
        # One level of fan-out: a single directory with tens of thousands of
        # entries is slow to list on every filesystem worth naming.
        return os.path.join(self._disk_dir, digest[:2], digest[2:])

    async def get_async(self, url: str) -> bytes | None:
        """Memory first, then disk. Disk hits are promoted into memory."""
        hit = self.get(url)
        if hit is not None:
            return hit
        if not self.disk_enabled:
            return None

        path = self._path_for(url)
        if not os.path.exists(path):
            return None
        try:
            raw, expires = await asyncio.to_thread(self._read_disk, path, url)
        except Exception as exc:
            log.debug("Disk cache read failed (%s): %s", url[:60], exc)
            return None
        if raw is None:
            return None

        self.disk_hits += 1
        self.hits += 1
        self.misses -= 1          # get() above already counted this as a miss
        remaining = max(1, int(expires - time.time()))
        self.put(url, raw, remaining)
        return raw

    def _read_disk(self, path: str, url: str):
        with open(path, "rb") as handle:
            head = handle.read(_HEADER.size)
            if len(head) < _HEADER.size:
                return None, 0.0
            magic, expires, url_len = _HEADER.unpack(head)
            if magic != _MAGIC:
                return None, 0.0
            if time.time() > expires:
                self._unlink(path)
                return None, 0.0
            # The digest is 256 bits, so a collision is not a real risk — but
            # serving one client's page to another would be a bad way to find
            # out, and comparing the URL costs nothing.
            stored_url = handle.read(url_len).decode("utf-8", "replace")
            if stored_url != url:
                return None, 0.0
            return handle.read(), expires

    def put_async(self, url: str, raw_response: bytes, ttl: int = 300):
        """Write through to both tiers. The disk write is fire-and-forget."""
        raw_response = strip_uncacheable_headers(raw_response)
        self.put(url, raw_response, ttl)
        if not self.disk_enabled or ttl <= 0:
            return
        size = len(raw_response)
        if size == 0 or size > self._disk_max // 8:
            return
        if url in self._pending:
            return
        self._pending.add(url)
        task = asyncio.create_task(self._write_disk_async(url, raw_response, ttl))
        # Hold a reference so the task is not garbage collected mid-write.
        task.add_done_callback(lambda _t, u=url: self._pending.discard(u))

    async def _write_disk_async(self, url: str, raw: bytes, ttl: int):
        try:
            await asyncio.to_thread(self._write_disk, url, raw, ttl)
        except Exception as exc:
            log.debug("Disk cache write failed (%s): %s", url[:60], exc)

    def _write_disk(self, url: str, raw: bytes, ttl: int):
        path = self._path_for(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        encoded = url.encode("utf-8", "replace")
        blob = (_HEADER.pack(_MAGIC, time.time() + ttl, len(encoded))
                + encoded + raw)
        # Write to a sibling and rename: a half-written cache file must never
        # be readable, and rename is atomic on every filesystem we target.
        tmp = path + ".tmp"
        with open(tmp, "wb") as handle:
            handle.write(blob)
        os.replace(tmp, path)
        self._disk_size += len(blob)
        if self._disk_size > self._disk_max:
            self._evict_disk()

    def _measure_disk(self) -> int:
        total = 0
        for root, _dirs, files in os.walk(self._disk_dir):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except OSError:
                    pass
        return total

    def _evict_disk(self):
        """Drop the least recently used quarter, by access time."""
        entries = []
        for root, _dirs, files in os.walk(self._disk_dir):
            for name in files:
                full = os.path.join(root, name)
                try:
                    stat = os.stat(full)
                except OSError:
                    continue
                entries.append((stat.st_atime, stat.st_size, full))
        entries.sort()
        target = self._disk_max * 3 // 4
        freed = 0
        for _atime, size, full in entries:
            if self._disk_size - freed <= target:
                break
            self._unlink(full)
            freed += size
        self._disk_size = max(0, self._disk_size - freed)
        log.info("Disk cache trimmed: freed %.0f MB", freed / 1e6)

    @staticmethod
    def _unlink(path: str):
        try:
            os.remove(path)
        except OSError:
            pass

    def clear_disk(self) -> int:
        """Delete every cached body. Returns bytes freed."""
        freed = self._disk_size
        for root, _dirs, files in os.walk(self._disk_dir):
            for name in files:
                self._unlink(os.path.join(root, name))
        self._disk_size = 0
        return freed

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "disk_hits": self.disk_hits,
            "hit_rate": round(self.hits / total * 100, 1) if total else 0.0,
            "memory_bytes": self._size,
            "disk_bytes": self._disk_size,
            "disk_enabled": self.disk_enabled,
            "disk_dir": self._disk_dir if self.disk_enabled else "",
        }

    # ── TTL policy ────────────────────────────────────────────────────

    @staticmethod
    def parse_ttl(raw_response: bytes, url: str) -> int:
        """Determine cache TTL from response headers and URL."""
        hdr_end = raw_response.find(b"\r\n\r\n")
        if hdr_end < 0:
            return 0
        hdr = raw_response[:hdr_end].decode(errors="replace").lower()

        # Don't cache errors or non-200
        if b"HTTP/1.1 200" not in raw_response[:20]:
            return 0
        # ``no-store`` is absolute. ``private`` excludes shared caches, and
        # this one is shared the moment lan_sharing is on, so honour it.
        #
        # Set-Cookie used to be treated the same way, and it cost most of the
        # cache: CDNs routinely staple an analytics or consent cookie onto
        # static assets — Wikipedia sends one with a PNG that is otherwise
        # marked immutable for a year — so nearly every image and font was
        # refused. Those responses are cacheable; what must not be reused is
        # the cookie, so it is stripped from the stored copy instead
        # (see :func:`strip_uncacheable_headers`).
        if "no-store" in hdr or "private" in hdr:
            return 0

        # Explicit max-age
        m = re.search(r"max-age=(\d+)", hdr)
        if m:
            return min(int(m.group(1)), CACHE_TTL_MAX)

        # Heuristic by content type / extension
        path = url.split("?")[0].lower()
        for ext in STATIC_EXTS:
            if path.endswith(ext):
                return CACHE_TTL_STATIC_LONG

        ct_m = re.search(r"content-type:\s*([^\r\n]+)", hdr)
        ct = ct_m.group(1) if ct_m else ""
        if "image/" in ct or "font/" in ct:
            return CACHE_TTL_STATIC_LONG
        if "text/css" in ct or "javascript" in ct:
            return CACHE_TTL_STATIC_MED
        if "text/html" in ct or "application/json" in ct:
            return 0  # don't cache dynamic content by default

        return 0
