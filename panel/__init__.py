"""Aras-GP Panel — web control surface for the Aras-GP domain-fronting relay.

The relay engine under ``src/`` uses flat imports (``from proxy_server import …``)
because it was written to run from ``main.py``. Importing the panel puts that
directory on ``sys.path`` so both entry points see the same modules.
"""

from __future__ import annotations

import sys

from .paths import SRC_DIR

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

__all__ = ["__version__"]
__version__ = "1.0.0"
