"""Share — VLESS configs for other people, on their own Cloudflare Worker.

Deliberately outside the relay. The relay is the project: a domain-fronting
proxy for the operator's own traffic. This is a separate capability that runs
someone else's traffic through a Worker, which is what carries the terms-of-
service risk, so it deploys its own script under its own name and shares no
state with the relay's deployment.

Nothing in ``engine/`` imports this, and this imports nothing from ``engine/``.
The relay keeps working whether this is deployed, disabled or deleted.
"""

from __future__ import annotations

__all__ = ["identity", "subscription", "worker"]
