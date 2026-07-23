"""Aras-GP Panel — web control surface for the Aras-GP domain-fronting relay.

The relay engine under ``engine/`` uses flat imports (``from proxy_server import …``)
because it was written to run from ``main.py``. Importing the panel puts that
directory on ``sys.path`` so both entry points see the same modules.
"""

from __future__ import annotations

import sys

from .paths import ENGINE_DIR

if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

__all__ = ["__version__"]
__version__ = "2.1.5"
