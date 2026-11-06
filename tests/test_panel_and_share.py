"""Tests for failover, the share helpers, config validation, and the deploy
path that renders the Cloudflare Worker source."""

import pytest

from panel.failover import FailoverMonitor, pick_next
from panel import cloudflare


class TestPickNext:
    def _relays(self):
        return [{"id": "a", "script_ids": ["s1"]},
                {"id": "b", "script_ids": ["s2"]},
                {"id": "c", "script_ids": ["s3"]}]

    def test_wraps_around(self):
        relays = self._relays()
        assert pick_next(relays, "b")["id"] == "c"
        assert pick_next(relays, "c")["id"] == "a"

    def test_unknown_active_starts_from_first(self):
        assert pick_next(self._relays(), "nope")["id"] == "a"

    def test_needs_two_usable(self):
        assert pick_next([self._relays()[0]], None) is None
        assert pick_next([], None) is None


class TestFailoverMonitor:
    # evaluate() sees *cumulative* totals, so every window must move both
    # counters for traffic to exist at all.

    def test_silence_is_not_failure(self):
        mon = FailoverMonitor()
        mon.enabled = True
        mon.grace = 60
        assert mon.evaluate(10, 0, None, now=0) is False      # healthy tick
        # The totals stop moving entirely: no traffic, no verdict, no switch.
        assert mon.evaluate(10, 0, None, now=10_000) is False

    def test_all_errors_for_grace_period_triggers_switch(self):
        mon = FailoverMonitor()
        mon.enabled = True
        mon.grace = 60
        assert mon.evaluate(10, 0, None, now=0) is False      # healthy
        assert mon.evaluate(20, 10, None, now=5) is False     # first bad window
        assert mon.evaluate(30, 20, None, now=120) is True    # grace passed

    def test_grace_period_not_reached(self):
        mon = FailoverMonitor()
        mon.enabled = True
        mon.grace = 60
        mon.evaluate(10, 0, None, now=0)
        mon.evaluate(20, 10, None, now=5)
        assert mon.evaluate(30, 20, None, now=30) is False

    def test_recent_success_stalls_the_switch(self):
        mon = FailoverMonitor()
        mon.enabled = True
        mon.grace = 60
        mon.evaluate(10, 0, None, now=0)
        mon.evaluate(20, 10, None, now=5)
        # A success just before this tick means some traffic got through.
        assert mon.evaluate(30, 20, last_success_at=115, now=120) is False

    def test_recovery(self):
        mon = FailoverMonitor()
        mon.enabled = True
        mon.grace = 60
        mon.evaluate(10, 0, None, now=0)
        mon.evaluate(20, 10, None, now=5)
        assert mon.evaluate(30, 20, None, now=10) is False    # still failing
        assert mon.evaluate(40, 21, None, now=15) is False    # mostly healthy
        assert mon._unhealthy_since is None


class TestShareIdentity:
    def test_paths_look_like_app_routes(self):
        from share.identity import random_path
        seen = {random_path() for _ in range(50)}
        for path in seen:
            assert path.startswith("/")
            assert ".." not in path
            assert "//" not in path
            assert path.count("/") >= 2

    def test_normalize_path_refuses_traversal(self):
        from share.identity import normalize_path
        assert normalize_path("/api/../../etc") == ""
        assert normalize_path("/api//x") == ""
        assert normalize_path("api/v1/ok", fallback="") == "/api/v1/ok"

    def test_script_names_always_valid(self):
        from share.identity import random_script_name
        import re
        pattern = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")
        for _ in range(50):
            assert pattern.match(random_script_name())


class TestSubscription:
    def test_vless_link_shape(self):
        import base64
        from share.subscription import vless_link, encode
        link = vless_link("TESTUUID", "w.example.com", "/ws/v1/abc123",
                          address="1.2.3.4", label="friend")
        assert link.startswith("vless://TESTUUID@1.2.3.4:443?")
        assert "type=ws" in link and "sni=w.example.com" in link
        blob = encode([link])
        assert base64.b64decode(blob).decode() == link

    def test_invalid_inputs_yield_empty(self):
        from share.subscription import vless_link
        assert vless_link("", "h", "/") == ""
        assert vless_link("u", "", "/") == ""


class TestConfiggen:
    def test_auth_key_generation_and_ensure(self):
        from panel import configgen
        key = configgen.generate_auth_key()
        assert len(key) >= configgen.MIN_AUTH_KEY_LENGTH
        config = {"auth_key": "short"}
        assert configgen.ensure_auth_key(config) is True
        assert config["auth_key"] == key or len(config["auth_key"]) >= 16
        assert configgen.ensure_auth_key(config) is False   # never rotated

    def test_hosts_map_parsing(self):
        from panel import configgen
        parsed = configgen.parse_hosts_map("youtube.com = 1.2.3.4\n#comment")
        assert parsed == {"youtube.com": "1.2.3.4"}
        with pytest.raises(configgen.ConfigError):
            configgen.parse_hosts_map("youtube.com = not-an-ip")

    def test_validate_errors(self):
        from panel import configgen
        config = {
            "auth_key": "x" * 40,
            "script_id": ["A" * 64],
            "listen_port": 8085,
            "socks5_port": 1080,
        }
        configgen.validate(config)                     # passes
        bad = dict(config, script_id=[""])
        with pytest.raises(configgen.ConfigError):
            configgen.validate(bad)
        same = dict(config, socks5_port=8085)
        with pytest.raises(configgen.ConfigError):
            configgen.validate(same)


class TestWorkerRendering:
    TEMPLATE_HEAD = (
        'const WORKER_URL = "myworker.workers.dev";\n'
        'const AUTH_KEY = "__ARAS_AUTH_KEY__";\n'
    )

    def test_substitutes_hostname_and_key(self):
        source = cloudflare.render_worker(
            "amber-gateway-1234", "acme-workers",
            source=self.TEMPLATE_HEAD + "export default {};",
            auth_key="SECRET",
        )
        assert 'const WORKER_URL = "amber-gateway-1234.acme-workers.workers.dev";' in source
        assert '__ARAS_AUTH_KEY__' not in source
        assert 'const AUTH_KEY = "SECRET";' in source

    def test_empty_key_deploys_unauthenticated(self):
        source = cloudflare.render_worker(
            "n", "s", source=self.TEMPLATE_HEAD, auth_key="",
        )
        assert 'const AUTH_KEY = "";' in source

    def test_key_with_specials_is_json_escaped(self):
        import json
        tricky = 'q"uote\\'
        source = cloudflare.render_worker(
            "n", "s", source=self.TEMPLATE_HEAD, auth_key=tricky,
        )
        assert f'const AUTH_KEY = {json.dumps(tricky)};' in source

    def test_validate_script_name(self):
        assert cloudflare.validate_script_name("Amber-1") == "amber-1"
        with pytest.raises(cloudflare.CloudflareError):
            cloudflare.validate_script_name("bad name!")
