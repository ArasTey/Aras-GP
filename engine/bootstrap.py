"""Start-up checks shared by both entry points.

Two things go wrong before any of this project's own code gets to run, and
both used to surface as a Python traceback that says nothing about the fix:

  * a dependency is not installed — the traceback names the module and leaves
    the reader to work out which requirements file mentions it, and with which
    interpreter to install it;
  * the console cannot encode what we print — on Windows, redirecting output
    to a file gives you the legacy code page, and the first Persian log line
    kills the process with a UnicodeEncodeError.

Neither belongs in the modules that trip over them, so both live here and are
called first thing by ``main.py`` and by ``python -m panel``.
"""

from __future__ import annotations

import os
import platform
import sys

#: Import name -> (pip requirement, what stops working without it).
KNOWN_PACKAGES: dict[str, tuple[str, str]] = {
    "flask": ("Flask>=3.0.0", "the control panel"),
    "requests": ("requests>=2.31.0", "Cloudflare deploys from the panel"),
    "cryptography": ("cryptography>=41.0.0", "HTTPS interception"),
    "h2": ("h2>=4.1.0", "HTTP/2 multiplexing"),
    "brotli": ("brotli>=1.1.0", "Brotli-compressed responses"),
    "zstandard": ("zstandard>=0.22.0", "Zstandard-compressed responses"),
    "certifi": ("certifi>=2024.1.0", "TLS certificate verification"),
}


def ensure_utf8_stdio() -> None:
    """Make stdout/stderr able to carry any text we log.

    The panel logs in Persian and the banner is drawn with box characters.
    Attached to a terminal, Python on Windows writes to the console through a
    UTF-16 API and both are fine — but the moment output is redirected (which
    the background runners do, into ``panel/data/panel.log``) the stream falls
    back to the process code page with strict error handling, and the first
    non-ASCII character raises. Reconfiguring costs nothing and removes the
    whole class of failure on every platform.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError, OSError):
            # Detached process (pythonw.exe) or an exotic stream: nothing to
            # reconfigure, and nothing that needs it.
            pass

    if platform.system() == "Windows":
        # Switch the console itself to UTF-8 so anything we did not write
        # through Python — a subprocess, a crash handler — renders too.
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass


def _install_command() -> str:
    """The exact command to run, for this interpreter and this platform.

    Always ``-r requirements.txt`` rather than a list of packages: an
    unquoted ``Flask>=3.0.0`` is a redirect in every shell this project runs
    under, cmd.exe included, so a copy-pasted package list would create a file
    called ``=3.0.0`` and install nothing.
    """
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if in_venv:
        launcher = "pip"
    elif platform.system() == "Windows":
        launcher = "py -m pip" if _has_py_launcher() else "python -m pip"
    else:
        launcher = "python3 -m pip"
    return f"{launcher} install -r requirements.txt"


def _has_py_launcher() -> bool:
    import shutil
    return shutil.which("py") is not None


def require_modules(*names: str) -> None:
    """Exit with an actionable message if any of *names* cannot be imported."""
    import importlib.util

    missing = [n for n in names if importlib.util.find_spec(n) is None]
    if not missing:
        return

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    windows = platform.system() == "Windows"
    launcher = "run.bat" if windows else "./run.sh"

    lines = [
        "",
        "Aras-GP cannot start: %d required package%s missing."
        % (len(missing), "" if len(missing) == 1 else "s are"),
        "",
    ]
    width = max(len(KNOWN_PACKAGES.get(n, (n, ""))[0]) for n in missing)
    for name in missing:
        requirement, purpose = KNOWN_PACKAGES.get(name, (name, ""))
        lines.append("  - %-*s  %s" % (width, requirement,
                                       f"({purpose})" if purpose else ""))
    lines += [
        "",
        "Install everything at once, from %s:" % root,
        "",
        "  %s" % _install_command(),
        "",
        "Or let the launcher build a virtualenv and do it for you:",
        "",
        "  %s" % launcher,
        "",
        "Running with: %s" % sys.executable,
    ]
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):
        lines += [
            "",
            "Note: that is a system-wide Python, not the project's .venv. If a",
            "      .venv already exists, use it instead:",
            "        %s" % (r".venv\Scripts\python -m panel" if windows
                            else ".venv/bin/python -m panel"),
        ]
    print("\n".join(lines), file=sys.stderr)
    raise SystemExit(1)
