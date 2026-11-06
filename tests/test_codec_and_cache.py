"""Tests for the codec and the response cache."""

import gzip
import zlib

from codec import decode
from cache import (
    ResponseCache,
    is_cacheable_status,
    response_status,
    strip_uncacheable_headers,
)

parse_ttl = ResponseCache.parse_ttl


def _http_response(body: bytes, extra: str = "", status: int = 200) -> bytes:
    head = (f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: text/css\r\n"
            f"Cache-Control: max-age=600\r\n{extra}\r\n")
    return head.encode() + body


class TestCodec:
    def test_gzip_roundtrip(self):
        raw = b"payload" * 100
        assert decode(gzip.compress(raw), "gzip") == raw

    def test_deflate_raw_fallback(self):
        # Some servers omit the zlib wrapper; the decoder must cope.
        compobj = zlib.compressobj(6, zlib.DEFLATED, -zlib.MAX_WBITS)
        raw = compobj.compress(b"abc") + compobj.flush()
        assert decode(raw, "deflate") == b"abc"

    def test_unknown_encoding_passthrough(self):
        assert decode(b"data", "brMadness") == b"data"

    def test_garbage_body_passthrough(self):
        assert decode(b"\x00\xff\xfe not gzip", "gzip") == \
            b"\x00\xff\xfe not gzip"

    def test_stacked_codings(self):
        raw = b"double"
        body = gzip.compress(gzip.compress(raw))
        assert decode(body, "gzip, gzip") == raw

    def test_depth_cap(self):
        raw = b"x"
        body = raw
        for _ in range(9):
            body = gzip.compress(body)
        # Nine gzip layers exceed the cap: must not spiral, must not crash.
        assert decode(body, ", ".join(["gzip"] * 9)) == body


class TestCacheStatusAndTtl:
    def test_status_parsing(self):
        assert response_status(b"HTTP/1.1 200 OK\r\n\r\n") == 200
        assert response_status(b"HTTP/2 404\r\n\r\n") == 404
        assert response_status(b"garbage") == 0

    def test_only_200_is_cacheable(self):
        assert is_cacheable_status(_http_response(b"", status=200))
        assert not is_cacheable_status(_http_response(b"", status=502))
        assert not is_cacheable_status(_http_response(b"", status=206))

    def test_no_store_refused(self):
        resp = b"HTTP/1.1 200 OK\r\nCache-Control: no-store\r\n\r\nbody"
        assert parse_ttl(resp, "https://x/style.css") == 0

    def test_private_refused(self):
        resp = b"HTTP/1.1 200 OK\r\nCache-Control: private, max-age=600\r\n\r\nbody"
        assert parse_ttl(resp, "https://x/style.css") == 0

    def test_max_age_honoured_and_capped(self):
        resp = b"HTTP/1.1 200 OK\r\nCache-Control: max-age=999999\r\n\r\nbody"
        assert parse_ttl(resp, "https://x/a.bin") <= 86400

    def test_html_not_cached_by_default(self):
        resp = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\nbody"
        assert parse_ttl(resp, "https://x/page") == 0

    def test_set_cookie_stripped_for_shared_replay(self):
        resp = _http_response(b"body", extra="Set-Cookie: a=b\r\n")
        kept = strip_uncacheable_headers(resp)
        assert b"Set-Cookie" not in kept
        assert b"body" in kept


class TestResponseCache:
    def test_put_get_and_lru_eviction(self):
        cache = ResponseCache(max_mb=1, disk_mb=0, disk_enabled=False)
        # 240 KB entries: small enough for put's per-entry guard (size cap is
        # max//4 = 256 KB), big enough that four of them overflow the 1 MB cap.
        body = b"A" * (240 * 1024)
        cache.put("https://x/a", body, ttl=60)
        cache.put("https://x/b", body, ttl=60)
        assert cache.get("https://x/a") == body        # touch: B is now coldest
        cache.put("https://x/c", body, ttl=60)
        cache.put("https://x/d", body, ttl=60)         # 960 KB held
        cache.put("https://x/e", body, ttl=60)         # 1.2 MB → evict oldest (b)
        assert cache.get("https://x/a") == body        # survives
        assert cache.get("https://x/b") is None        # evicted
        assert cache.get("https://x/c") == body

    def test_expired_entry_refused(self):
        cache = ResponseCache(max_mb=1, disk_mb=0, disk_enabled=False)
        cache.put("https://x/a", b"A", ttl=-1)
        assert cache.get("https://x/a") is None

    def test_hresult_never_stored(self):
        import asyncio
        cache = ResponseCache(max_mb=1, disk_mb=0, disk_enabled=False)

        async def store_bad():
            cache.put_async("https://x/e", _http_response(b"", status=502), ttl=60)
            return cache.get("https://x/e")

        assert asyncio.run(store_bad()) is None

    def test_get_async_promotes_disk(self, tmp_path):
        import asyncio
        cache = ResponseCache(max_mb=1, disk_mb=10, disk_dir=str(tmp_path),
                              disk_enabled=True)
        resp = _http_response(b"from disk")

        async def cold_memory_read():
            # put_async writes memory synchronously and disk fire-and-forget.
            # Wait for the in-flight write to finish instead of sleeping a fixed
            # interval: on a loaded runner 50ms was not enough and the disk read
            # came back empty, failing the test for a scheduling reason.
            cache.put_async("https://x/a", resp, ttl=60)

            async def drain():
                while "https://x/a" in cache._pending:
                    await asyncio.sleep(0.001)

            await asyncio.wait_for(drain(), timeout=5)
            cache._store.clear()
            cache._size = 0
            return await cache.get_async("https://x/a")

        assert asyncio.run(cold_memory_read()) == resp
        assert cache.disk_hits == 1
