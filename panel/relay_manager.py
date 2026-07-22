"""Flask ↔ relay bridge.

**Chosen integration model: in-process worker thread with a private asyncio
event loop.**

The relay is an asyncio application and Flask is a synchronous WSGI app, so the
two cannot share a loop. Rather than shelling out to ``main.py`` and scraping
stdout, the panel starts a dedicated thread, gives it its own event loop, and
constructs :class:`~proxy_server.ProxyServer` inside it. The panel keeps a
reference to that object, which is what makes the live dashboard possible:
``fronter.stats_snapshot()`` and the per-user accounting tables are read
directly from the running relay instead of being guessed at from log output.

Every call that touches relay state is marshalled back onto the relay loop with
``run_coroutine_threadsafe`` — the relay's dictionaries are only ever read from
the thread that mutates them, so no lock is needed and no snapshot can tear.

Trade-off, stated plainly: relay and panel share a process, so an unhandled
crash in one takes down the other, and stopping the relay cannot reclaim memory
the way killing a subprocess would. In exchange the dashboard is genuinely live
rather than a log parser, which is the whole point of the product.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
from collections import deque

from cert_installer import is_ca_trusted          # from src/
from mitm import CA_CERT_FILE                     # from src/
from proxy_server import ProxyServer              # from src/

log = logging.getLogger("panel.relay")

SAMPLE_INTERVAL = 5.0     # seconds between dashboard samples
MAX_SAMPLES = 720         # ≈ 1 hour of history at 5 s
MAX_LOG_LINES = 400
PERSIST_EVERY = 60.0      # how often per-user byte counters are flushed to disk


#: Loggers the relay engine actually uses (see ``src/*.py``). The status page
#: shows only these — attaching the buffer to the root logger would drown the
#: relay's output in Werkzeug's HTTP access lines from the panel itself.
RELAY_LOGGERS = frozenset({
    "Proxy", "Fronter", "Accounts", "MITM", "Cert", "Codec",
    "H2", "LAN", "Scanner", "Main", "asyncio", "panel.relay",
})


class RelayLogBuffer(logging.Handler):
    """Ring buffer of relay log records for the panel's status page."""

    def __init__(self, capacity: int = MAX_LOG_LINES):
        super().__init__()
        self.records: deque = deque(maxlen=capacity)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                                            datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        # Keep the relay's own loggers (and their children) only.
        root = record.name.split(".")[0]
        if record.name not in RELAY_LOGGERS and root not in RELAY_LOGGERS:
            return
        try:
            self.records.append({
                "t": record.created,
                "level": record.levelname,
                "logger": record.name,
                "text": self.format(record),
            })
        except Exception:
            pass

    def tail(self, limit: int = 200, level: str | None = None) -> list[dict]:
        items = list(self.records)
        if level:
            wanted = level.upper()
            items = [r for r in items if r["level"] == wanted]
        return items[-limit:]

    def clear(self) -> None:
        self.records.clear()


class RelayManager:
    """Owns the relay's lifecycle and exposes it to the Flask layer."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: ProxyServer | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready = threading.Event()
        self._lock = threading.RLock()

        self.config: dict | None = None
        self.started_at: float | None = None
        self.last_error: str | None = None
        self.last_success_at: float | None = None

        self.logs = RelayLogBuffer()
        self._samples: deque = deque(maxlen=MAX_SAMPLES)
        self._sampler: threading.Thread | None = None
        self._sampler_stop = threading.Event()
        self._last_totals = (0, 0)   # (requests, bytes) at previous sample

        #: Optional callback run on the sampler thread every
        #: :data:`PERSIST_EVERY` seconds. The panel points this at
        #: ``users.persist_live_usage`` so byte counters survive a hard kill —
        #: set here rather than imported, because users.py imports this module.
        self.sample_hook = None
        self._last_hook = 0.0

    # ── lifecycle ─────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._server)

    def start(self, config: dict, timeout: float = 20.0) -> tuple[bool, str]:
        """Boot the relay. Returns ``(ok, message)``."""
        with self._lock:
            if self.running:
                return False, "رله از قبل در حال اجراست."

            self.config = dict(config)
            self.last_error = None
            self._ready.clear()

            self._attach_log_handler(self.config.get("log_level", "INFO"))

            self._thread = threading.Thread(
                target=self._thread_main, name="aras-relay", daemon=True,
            )
            self._thread.start()

            if not self._ready.wait(timeout):
                self.stop()
                return False, "رله در زمان مقرر بالا نیامد."
            if self.last_error:
                message = self.last_error
                self.stop()
                return False, message

            self.started_at = time.time()
            self._start_sampler()
            return True, "رله راه‌اندازی شد."

    def stop(self, timeout: float = 15.0) -> tuple[bool, str]:
        with self._lock:
            was_running = self.running
            self._stop_sampler()
            loop, event, thread = self._loop, self._stop_event, self._thread
            if loop is not None and event is not None and not loop.is_closed():
                loop.call_soon_threadsafe(event.set)
            if thread is not None:
                thread.join(timeout)
                if thread.is_alive():
                    log.warning("Relay thread did not exit within %.0fs", timeout)
            self._thread = None
            self._loop = None
            self._server = None
            self._stop_event = None
            self.started_at = None
            return True, ("رله متوقف شد." if was_running else "رله از قبل خاموش بود.")

    def restart(self, config: dict | None = None) -> tuple[bool, str]:
        target = config or self.config
        if target is None:
            return False, "کانفیگی برای راه‌اندازی مجدد موجود نیست."
        if self.running:
            self.stop()
        return self.start(target)

    # ── worker thread ─────────────────────────────────────────────────

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        loop.set_exception_handler(self._loop_exception_handler)
        try:
            loop.run_until_complete(self._run())
        except Exception as exc:
            self.last_error = str(exc)
            log.error("Relay thread crashed: %s", exc)
        finally:
            with contextlib.suppress(Exception):
                loop.run_until_complete(loop.shutdown_asyncgens())
            with contextlib.suppress(Exception):
                loop.close()
            self._server = None
            self._ready.set()   # unblock start() if we died before signalling

    async def _run(self) -> None:
        self._stop_event = asyncio.Event()
        try:
            server = ProxyServer(self.config)
        except Exception as exc:
            self.last_error = str(exc)
            log.error("Relay could not be constructed: %s", exc)
            self._ready.set()
            return

        self._server = server
        serve_task = asyncio.create_task(server.start())
        stop_task = asyncio.create_task(self._stop_event.wait())

        # Give the listeners a beat to bind so a port clash surfaces as a
        # start() failure instead of a "running" relay nobody can connect to.
        await asyncio.sleep(0.4)
        if serve_task.done() and serve_task.exception() is not None:
            self.last_error = str(serve_task.exception())
            log.error("Relay failed to start: %s", self.last_error)
            self._server = None
            stop_task.cancel()
            self._ready.set()
            return

        self._ready.set()
        try:
            await asyncio.wait({serve_task, stop_task},
                               return_when=asyncio.FIRST_COMPLETED)
            if serve_task.done() and not serve_task.cancelled():
                exc = serve_task.exception()
                if exc is not None:
                    self.last_error = str(exc)
                    log.error("Relay stopped with an error: %s", exc)
        finally:
            for task in (serve_task, stop_task):
                task.cancel()
            for task in (serve_task, stop_task):
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            with contextlib.suppress(Exception):
                await server.stop()
            self._server = None

    def _loop_exception_handler(self, loop, context):
        exc = context.get("exception")
        source = str(context.get("handle") or "")
        # Benign Windows socket-teardown race, same suppression as main.py.
        if isinstance(exc, ConnectionResetError) and "_call_connection_lost" in source:
            return
        log.debug("[relay asyncio] %s", context.get("message", context))

    def _attach_log_handler(self, level_name: str) -> None:
        """Route the relay's loggers into the panel's ring buffer."""
        try:
            level = getattr(logging, str(level_name).upper())
        except AttributeError:
            level = logging.INFO
        self.logs.setLevel(logging.DEBUG)
        root = logging.getLogger()
        if self.logs not in root.handlers:
            root.addHandler(self.logs)
        for name in RELAY_LOGGERS:
            if name != "asyncio":     # asyncio at DEBUG is pure noise
                logging.getLogger(name).setLevel(level)

    # ── talking to the running relay ──────────────────────────────────

    def _call(self, coro_factory, timeout: float = 5.0, default=None):
        """Run ``coro_factory()`` on the relay loop and wait for its result."""
        loop, server = self._loop, self._server
        if loop is None or server is None or loop.is_closed():
            return default
        try:
            future = asyncio.run_coroutine_threadsafe(coro_factory(server), loop)
            return future.result(timeout)
        except Exception as exc:
            log.debug("Relay call failed: %s", exc)
            return default

    def stats(self) -> dict:
        """Live snapshot straight from the running DomainFronter."""
        async def snapshot(server):
            data = server.fronter.stats_snapshot()
            data["accounts"] = server.accounts.snapshot()
            data["account_totals"] = server.accounts.totals()
            data["auth_required"] = server.accounts.required
            data["socks_active"] = server.socks_active
            return data

        empty = {
            "per_site": [], "blacklisted_scripts": [], "sni_rotation": [],
            "parallel_relay": 0, "accounts": [], "auth_required": False,
            "socks_active": False,
            "account_totals": {"accounts": 0, "active": 0, "connections": 0,
                               "up_bytes": 0, "down_bytes": 0},
        }
        return self._call(snapshot, default=empty) or empty

    def sync_accounts(self, user_records: list[dict], required: bool) -> bool:
        """Hot-reload the proxy user table into the live relay."""
        async def apply(server):
            server.accounts.load(user_records)
            server.accounts.set_required(required)
            server.accounts.sweep()
            return True

        return bool(self._call(apply, default=False))

    def disconnect_user(self, username: str) -> int:
        async def cut(server):
            account = server.accounts.get(username)
            return account.disconnect_all() if account else 0

        return int(self._call(cut, default=0) or 0)

    def reset_user_usage(self, username: str) -> bool:
        async def reset(server):
            return server.accounts.reset_usage(username)

        return bool(self._call(reset, default=False))

    def test_relay(self, url: str = "https://www.gstatic.com/generate_204",
                   timeout: float = 30.0) -> dict:
        """Send one real request through the relay and report the result.

        This is the honest answer to "is the GAS/Worker chain alive?" — it
        exercises the exact path normal traffic takes, rather than inferring
        health from counters.
        """
        if not self.running:
            return {"ok": False, "error": "رله در حال اجرا نیست."}

        async def probe(server):
            started = time.monotonic()
            raw = await server.fronter.relay(
                "GET", url,
                {"Host": url.split("/")[2], "User-Agent": "Aras-GP-Panel/1.0"},
                b"",
            )
            elapsed = (time.monotonic() - started) * 1000
            status = 0
            if raw:
                first = raw.split(b"\r\n", 1)[0].decode("latin-1", "replace")
                parts = first.split(" ")
                if len(parts) > 1 and parts[1].isdigit():
                    status = int(parts[1])
            return {"status": status, "ms": round(elapsed, 1),
                    "bytes": len(raw or b"")}

        result = self._call(probe, timeout=timeout)
        if not result:
            return {"ok": False, "error": "پاسخی از رله دریافت نشد."}
        ok = 200 <= result["status"] < 400 or result["status"] == 204
        if ok:
            self.last_success_at = time.time()
        return {"ok": ok, **result}

    # ── sampling for the dashboard chart ──────────────────────────────

    def _start_sampler(self) -> None:
        self._sampler_stop.clear()
        self._samples.clear()
        self._last_totals = (0, 0)
        self._sampler = threading.Thread(
            target=self._sample_loop, name="aras-sampler", daemon=True,
        )
        self._sampler.start()

    def _stop_sampler(self) -> None:
        self._sampler_stop.set()
        if self._sampler and self._sampler.is_alive():
            self._sampler.join(timeout=SAMPLE_INTERVAL + 1)
        self._sampler = None

    def _sample_loop(self) -> None:
        while not self._sampler_stop.wait(SAMPLE_INTERVAL):
            if not self.running:
                continue
            try:
                snapshot = self.stats()
                requests = sum(row["requests"] for row in snapshot["per_site"])
                total_bytes = sum(row["bytes"] for row in snapshot["per_site"])
                prev_requests, prev_bytes = self._last_totals
                delta_bytes = max(0, total_bytes - prev_bytes)
                delta_requests = max(0, requests - prev_requests)
                self._last_totals = (requests, total_bytes)

                # Any forward progress means the GAS/Worker chain answered.
                if delta_requests or delta_bytes:
                    self.last_success_at = time.time()

                self._samples.append({
                    "t": time.time(),
                    "bytes": total_bytes,
                    "requests": requests,
                    "bps": delta_bytes / SAMPLE_INTERVAL,
                    "rps": delta_requests / SAMPLE_INTERVAL,
                    "connections": snapshot["account_totals"]["connections"],
                })

                # Flush per-user usage so a crash costs at most one interval
                # of accounting rather than the whole billing period.
                now = time.time()
                if self.sample_hook and now - self._last_hook >= PERSIST_EVERY:
                    self._last_hook = now
                    try:
                        self.sample_hook()
                    except Exception as exc:
                        log.debug("Sample hook error: %s", exc)
            except Exception as exc:
                log.debug("Sampler error: %s", exc)

    def series(self, limit: int = 120) -> list[dict]:
        return list(self._samples)[-limit:]

    # ── status ────────────────────────────────────────────────────────

    def status(self) -> dict:
        config = self.config or {}
        snapshot = self.stats() if self.running else None
        per_site = snapshot["per_site"] if snapshot else []
        script_ids = config.get("script_ids") or config.get("script_id") or ""
        if isinstance(script_ids, str):
            script_ids = [script_ids] if script_ids else []

        return {
            "running": self.running,
            "started_at": self.started_at,
            "uptime": (time.time() - self.started_at) if self.started_at else 0,
            "last_error": self.last_error,
            "last_success_at": self.last_success_at,
            "listen_host": config.get("listen_host", "127.0.0.1"),
            "listen_port": config.get("listen_port", 8085),
            "socks5_enabled": config.get("socks5_enabled", True),
            "socks5_port": config.get("socks5_port", 1080),
            # Configured is not the same as listening: a busy SOCKS port is
            # logged and tolerated by the engine, so report the real state.
            "socks5_active": bool(snapshot["socks_active"]) if snapshot else False,
            "lan_sharing": config.get("lan_sharing", False),
            "front_domain": config.get("front_domain", "www.google.com"),
            "google_ip": config.get("google_ip", ""),
            "script_count": len(script_ids),
            "parallel_relay": config.get("parallel_relay", 1),
            "auth_required": bool(snapshot["auth_required"]) if snapshot else False,
            "sites": len(per_site),
            "requests": sum(row["requests"] for row in per_site),
            "errors": sum(row["errors"] for row in per_site),
            "bytes": sum(row["bytes"] for row in per_site),
            "avg_ms": round(
                sum(row["avg_ms"] * row["requests"] for row in per_site)
                / max(1, sum(row["requests"] for row in per_site)), 1,
            ),
            "connections": snapshot["account_totals"]["connections"] if snapshot else 0,
            "ca_present": os.path.exists(CA_CERT_FILE),
            "ca_trusted": _ca_trusted_cached(),
            "ca_path": CA_CERT_FILE,
        }


# ── CA trust check (cached: the OS call is slow on macOS/Windows) ──────

_ca_cache: dict = {"value": None, "at": 0.0}
_CA_CACHE_TTL = 30.0


def _ca_trusted_cached(force: bool = False) -> bool:
    now = time.time()
    if force or _ca_cache["value"] is None or now - _ca_cache["at"] > _CA_CACHE_TTL:
        try:
            _ca_cache["value"] = bool(is_ca_trusted(CA_CERT_FILE))
        except Exception:
            _ca_cache["value"] = False
        _ca_cache["at"] = now
    return bool(_ca_cache["value"])


def refresh_ca_status() -> bool:
    return _ca_trusted_cached(force=True)


manager = RelayManager()
