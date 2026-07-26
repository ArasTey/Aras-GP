"""Per-deployment identity: the names and paths that make one share Worker
look like nothing in particular.

Everything here is random per deployment rather than derived from the operator,
their account, or the project. A name like ``aras-share`` on a public
``workers.dev`` subdomain announces both what the script is and which tool
produced it, which is exactly what someone enumerating deployments is looking
for. These read as ordinary application names instead.

Names are drawn from a wordlist rather than being hex strings, because a script
called ``a3f9c2`` is itself a signal — it looks like something hiding. The
entropy comes from the combination plus a numeric tail, not from looking random.
"""

from __future__ import annotations

import re
import secrets
import uuid as _uuid

#: Ordinary infrastructure words. Nothing here hints at proxying, and nothing
#: is drawn from the project's own vocabulary.
_ADJECTIVES = (
    "swift", "quiet", "amber", "north", "clear", "solid", "bright", "calm",
    "prime", "urban", "coral", "linen", "maple", "olive", "cobalt", "ivory",
    "quartz", "cedar", "harbor", "meadow", "summit", "lunar", "delta", "vivid",
)
_NOUNS = (
    "gateway", "bridge", "portal", "beacon", "anchor", "signal", "vector",
    "matrix", "vertex", "cluster", "runtime", "service", "handler", "adapter",
    "channel", "session", "monitor", "registry", "pipeline", "endpoint",
    "workspace", "instance", "connector", "dispatch",
)

#: Path segments that look like a real application's routes.
_PATH_WORDS = (
    "api", "v1", "v2", "ws", "socket", "stream", "live", "edge", "gw",
    "hub", "sync", "events", "feed", "link", "node", "relay2", "bridge",
    "assets", "static", "cdn", "media", "data", "core", "app",
)

#: Cloudflare script names: lowercase letters, digits and hyphens, 1-63 chars,
#: no leading or trailing hyphen.
_SCRIPT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")


def random_script_name() -> str:
    """A Worker name that reads like an ordinary service.

    Deployed to ``<name>.<subdomain>.workers.dev``, so it is publicly visible
    and worth not naming after this project.
    """
    name = (f"{secrets.choice(_ADJECTIVES)}-{secrets.choice(_NOUNS)}"
            f"-{secrets.randbelow(9000) + 1000}")
    # The generator cannot produce an invalid name, but the value goes straight
    # to Cloudflare's API and a rejected name would surface as an opaque
    # deploy failure, so it is checked rather than assumed.
    return name if _SCRIPT_NAME_RE.match(name) else f"service-{secrets.token_hex(4)}"


def random_path(segments: int = 2) -> str:
    """A URL path that does not look like a proxy endpoint.

    Two segments plus a short random tail: enough that scanning for a fixed
    path finds nothing, while still looking like a route an application would
    actually serve.
    """
    parts = [secrets.choice(_PATH_WORDS) for _ in range(max(1, segments))]
    parts.append(secrets.token_hex(3))
    return "/" + "/".join(parts)


def random_uuid() -> str:
    return str(_uuid.uuid4())


def random_token(nbytes: int = 16) -> str:
    return secrets.token_urlsafe(nbytes)


def normalize_path(path, fallback: str = "") -> str:
    """Coerce a path to a safe single-line URL path, or fall back.

    Rejected rather than repaired when it contains anything that would not
    survive a URL, because a silently-altered path stops matching the Worker's
    binding and the failure surfaces far from the cause.
    """
    text = str(path or "").strip()
    if not text:
        return fallback
    if not text.startswith("/"):
        text = "/" + text
    if not re.fullmatch(r"/[A-Za-z0-9._~\-/]{1,120}", text):
        return fallback
    # The Worker compares this literally, so anything a client might rewrite
    # before sending has to be refused here or the config silently stops
    # matching. Clients collapse "//" and resolve "..", and a path that has
    # been resolved on the way out no longer equals the one bound to the
    # Worker — which fails as "config does not work", far from the cause.
    if ".." in text.split("/") or "//" in text:
        return fallback
    return text.rstrip("/") or "/"


def valid_script_name(name) -> bool:
    return bool(_SCRIPT_NAME_RE.match(str(name or "")))
