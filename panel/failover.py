"""Automatic failover between saved relays.

The rule the operator asked for: if the active relay is unreachable or keeps
erroring for more than a minute, move to the next saved relay by itself.

**Detection is passive.** Nothing here sends a probe on a timer. Health is read
off the traffic that is already flowing — the relay engine's own per-host
counters — because a censorship tool that heartbeats every few seconds both
wastes the operator's Apps Script quota and creates a periodic, fingerprintable
pattern on the wire. When there is no traffic there is no signal, and no signal
means no action: an idle relay is not a broken one.

A single active probe is allowed in exactly one case — traffic is failing and we
are about to switch anyway — to avoid flapping away from a relay because of one
bad site. That probe costs one request per failover decision, not one per tick.

The monitor runs inside :class:`RelayManager`'s existing sampler thread. It
starts no thread, opens no socket and allocates nothing per tick beyond a few
integers.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger("panel.failover")

#: How long the active relay must look broken before we switch.
DEFAULT_GRACE_SECONDS = 60.0

#: Never switch more often than this, so a bad network cannot make the panel
#: cycle through every saved relay in a few seconds.
MIN_SWITCH_INTERVAL = 90.0


class FailoverMonitor:
    """Decides when to move to the next saved relay.

    The class holds no references to the store or the relay manager; the caller
    injects them. That keeps it importable from tests without a live panel and
    avoids an import cycle with ``relay_manager``.
    """

    def __init__(self):
        self.enabled = False
        self.grace = DEFAULT_GRACE_SECONDS

        self._unhealthy_since: float | None = None
        self._last_switch = 0.0
        self._last_counts = (0, 0)      # (requests, errors) at previous sample
        self.last_reason = ""
        self.switch_count = 0
        self.last_switch_at: float | None = None

    # ── state the UI reads ────────────────────────────────────────────

    def snapshot(self) -> dict:
        unhealthy_for = (
            time.time() - self._unhealthy_since if self._unhealthy_since else 0.0
        )
        return {
            "enabled": self.enabled,
            "grace": self.grace,
            "unhealthy_for": round(unhealthy_for, 1),
            "switches": self.switch_count,
            "last_switch_at": self.last_switch_at,
            "last_reason": self.last_reason,
        }

    def reset(self) -> None:
        """Forget accumulated health after a restart or a manual switch."""
        self._unhealthy_since = None
        self._last_counts = (0, 0)

    # ── the decision ──────────────────────────────────────────────────

    def evaluate(self, requests: int, errors: int, last_success_at: float | None,
                 now: float | None = None) -> bool:
        """Fold one sample in. Returns True when a switch is due.

        ``requests`` and ``errors`` are cumulative totals from the relay's own
        counters; we only ever look at how much they moved since last time.
        """
        now = now or time.time()
        prev_requests, prev_errors = self._last_counts
        self._last_counts = (requests, errors)

        delta_requests = max(0, requests - prev_requests)
        delta_errors = max(0, errors - prev_errors)

        if not self.enabled:
            self._unhealthy_since = None
            return False

        # No traffic in this window: no evidence either way. Explicitly do not
        # treat silence as failure — that is what would force a needless probe.
        if delta_requests == 0:
            return False

        healthy = delta_errors < delta_requests
        if healthy:
            if self._unhealthy_since is not None:
                log.info("Relay recovered after %.0fs",
                         now - self._unhealthy_since)
            self._unhealthy_since = None
            return False

        # Every request in this window failed.
        if self._unhealthy_since is None:
            self._unhealthy_since = now
            log.warning("Relay looks unhealthy — %d/%d requests failed",
                        delta_errors, delta_requests)
            return False

        if now - self._unhealthy_since < self.grace:
            return False

        # A recent success means traffic is getting through despite errors on
        # some hosts; that is a site problem, not a relay problem.
        if last_success_at and now - last_success_at < self.grace:
            return False

        if now - self._last_switch < MIN_SWITCH_INTERVAL:
            return False

        self.last_reason = (
            f"{int(now - self._unhealthy_since)} ثانیه خطای پیوسته"
        )
        return True

    def note_switch(self, now: float | None = None) -> None:
        now = now or time.time()
        self._last_switch = now
        self.last_switch_at = now
        self.switch_count += 1
        self.reset()


def pick_next(relays: list[dict], active_id: str | None) -> dict | None:
    """The relay to try after ``active_id``, wrapping around the list.

    ``relays`` is the ordered list from the store. Returns None when there is
    nowhere better to go — one relay, or none.
    """
    usable = [r for r in relays if r.get("script_ids")]
    if len(usable) < 2:
        return None
    ids = [r["id"] for r in usable]
    try:
        index = ids.index(active_id)
    except ValueError:
        return usable[0]
    return usable[(index + 1) % len(usable)]
