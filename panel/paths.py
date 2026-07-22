"""Filesystem layout for the Aras-GP Panel.

Everything the panel writes lives under ``panel/data/`` next to the package,
so the relay repository stays clean and a single ``.gitignore`` entry keeps
secrets out of version control.
"""

from __future__ import annotations

import os

PANEL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PANEL_DIR)
ENGINE_DIR = os.path.join(PROJECT_ROOT, "engine")

DATA_DIR = os.environ.get("ARAS_DATA_DIR") or os.path.join(PANEL_DIR, "data")
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")

PANEL_STATE_FILE = os.path.join(DATA_DIR, "panel.json")
LICENSE_FILE = os.path.join(DATA_DIR, "license.key")

# Relay artefacts (shared with main.py / setup.py).
CONFIG_FILE = os.environ.get("DFT_CONFIG") or os.path.join(PROJECT_ROOT, "config.json")
CONFIG_EXAMPLE_FILE = os.path.join(PROJECT_ROOT, "config.example.json")
CA_DIR = os.path.join(PROJECT_ROOT, "ca")

# Deploy templates shipped with the relay.
WORKER_TEMPLATE = os.path.join(PROJECT_ROOT, "deploy", "cloudflare-worker", "worker.js")
GAS_TEMPLATE = os.path.join(PROJECT_ROOT, "deploy", "gas", "Code.gs")
FORWARDER_ENV = os.path.join(PROJECT_ROOT, "deploy", "upstream_forwarder", ".env")


def ensure_dirs() -> None:
    """Create the panel's private directories with owner-only permissions."""
    for path in (DATA_DIR, PROFILES_DIR):
        os.makedirs(path, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass  # Windows / exotic filesystems — best effort only
