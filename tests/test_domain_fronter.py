"""Tests for the relay engine's pure response-assembly helpers."""

import base64

from domain_fronter import DomainFronter


class TestSplitSetCookie:
    def test_single_cookie_passes_through(self):
        blob = "SID=abc; Path=/; Expires=Wed, 21 Oct 2026 07:28:00 GMT"
        assert DomainFronter._split_set_cookie(blob) == [blob]

    def test_two_cookies_split_but_date_comma_kept(self):
        blob = ("SID=a; Expires=Wed, 21 Oct 2026 07:28:00 GMT, "
                "HSID=b; Expires=Thu, 22 Oct 2026 07:28:00 GMT")
        parts = DomainFronter._split_set_cookie(blob)
        assert len(parts) == 2
        assert parts[0].endswith("07:28:00 GMT")
        assert parts[1].endswith("07:28:00 GMT")

    def test_empty(self):
        assert DomainFronter._split_set_cookie("") == []
        assert DomainFronter._split_set_cookie(None) == []


class TestRangeValidation:
    def test_parse_content_range_ok(self):
        parsed = DomainFronter._parse_content_range("bytes 0-262143/1048576")
        assert parsed == (0, 262143, 1048576)

    def test_parse_content_range_garbage(self):
        assert DomainFronter._parse_content_range("nonsense") is None
        assert DomainFronter._parse_content_range("bytes 10-5/100") is None
        assert DomainFronter._parse_content_range("bytes 0-99/50") is None

    def test_validate_accepts_correct_chunk(self):
        err = DomainFronter._validate_range_response(
            206, {"content-range": "bytes 100-199/1000"},
            b"x" * 100, 100, 199, 1000,
        )
        assert err is None

    def test_validate_rejects_wrong_start(self):
        err = DomainFronter._validate_range_response(
            206, {"content-range": "bytes 200-299/1000"},
            b"x" * 100, 100, 199, 1000,
        )
        assert "mismatch" in err

    def test_validate_rejects_short_body(self):
        err = DomainFronter._validate_range_response(
            206, {"content-range": "bytes 100-199/1000"},
            b"x" * 99, 100, 199, 1000,
        )
        assert "short chunk" in err

    def test_validate_rejects_non_206(self):
        err = DomainFronter._validate_range_response(
            200, {}, b"body", 0, 99, 1000,
        )
        assert "status 200" in err


class TestRewrite206:
    def test_status_becomes_200_and_content_range_dropped(self):
        raw = (
            b"HTTP/1.1 206 Partial Content\r\n"
            b"Content-Type: video/mp4\r\n"
            b"Content-Range: bytes 0-99/1000\r\n"
            b"Content-Length: 100\r\n\r\n" + b"y" * 100
        )
        out = DomainFronter._rewrite_206_to_200(raw)
        head, body = out.split(b"\r\n\r\n", 1)
        assert body == b"y" * 100
        assert head.startswith(b"HTTP/1.1 200 OK")
        assert b"Content-Range" not in head
        assert b"Content-Length: 100" in head

    def test_no_separator_is_returned_untouched(self):
        assert DomainFronter._rewrite_206_to_200(b"garbage") == b"garbage"


class TestPayloadBuild:
    def test_auth_key_added_on_encode(self):
        fr = DomainFronter.__new__(DomainFronter)
        fr.auth_key = "secret123"
        payload = {"m": "GET", "u": "https://x/"}
        encoded = fr._encode_relay_payload(payload)
        assert b'"k": "secret123"' in encoded or b'"k":"secret123"' in encoded

    def test_stripped_leak_headers(self):
        fr = DomainFronter.__new__(DomainFronter)
        fr.auth_key = ""
        payload = fr._build_payload(
            "GET", "https://x/",
            {"x-forwarded-for": "1.2.3.4", "via": "proxy", "accept": "a"},
            b"",
        )
        assert "x-forwarded-for" not in payload["h"]
        assert "via" not in payload["h"]
        assert payload["h"]["accept"] == "a"

    def test_small_body_base64_roundtrip(self):
        fr = DomainFronter.__new__(DomainFronter)
        fr.auth_key = ""
        body = b"hello"
        payload = fr._build_payload("POST", "https://x/", {}, body)
        assert base64.b64decode(payload["b"]) == body
