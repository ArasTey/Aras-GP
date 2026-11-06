"""Shared test setup: put engine/ and the project root on sys.path.

The engine uses flat imports (``from codec import …``), so every test that
imports an engine module needs ``engine/`` importable by module name. Importing
the panel needs the project root for the ``panel`` package itself, and its
``__init__`` adds ``engine/`` again.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENGINE = os.path.join(_ROOT, "engine")

for path in (_ENGINE, _ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)
