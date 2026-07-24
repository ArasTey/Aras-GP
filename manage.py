#!/usr/bin/env python3
"""Aras-GP panel manager — one script, every OS.

A single menu for installing, running and maintaining the panel, in the spirit
of x-ui's `x-ui` command but written in Python so it behaves identically on
Linux, macOS and Windows — which matters because the panel itself already runs
on all three, and a bash-only manager would have stranded Windows.

Nothing here imports the project or needs the virtualenv: the menu is pure
standard library, so it runs on a machine where dependencies were never
installed (that is what the *Install* action is for). It drives the panel by
launching `.venv/bin/python -m panel` as a detached process and tracking it
with a PID file, exactly as the shell runners did, plus a real listening-port
check so "Running" means the panel actually answers.

Run it with `python3 manage.py`, or through the `agp.sh` / `agp.bat` wrappers,
or — after Install offers it — the global `agp` command (just type `agp`).

The menu is intentionally in English: the panel's web UI is Persian, but a
terminal box drawn around right-to-left text reorders and looks broken in most
shells, so the manager keeps its labels ASCII and aligned.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import time
import webbrowser
from pathlib import Path

# ── layout ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

VENV_DIR = ROOT / ".venv"
VENV_PY = (VENV_DIR / ("Scripts/python.exe" if IS_WINDOWS else "bin/python"))
# Honour ARAS_DATA_DIR just like the panel does, so the two always agree on
# where state lives and a relocated install keeps working.
DATA_DIR = Path(os.environ.get("ARAS_DATA_DIR") or (ROOT / "panel" / "data"))
PID_FILE = DATA_DIR / "panel.pid"
LOG_FILE = DATA_DIR / "panel.log"
STATE_FILE = DATA_DIR / "manage.json"       # port/host/autostart the manager owns
PANEL_JSON = DATA_DIR / "panel.json"        # admin hash, secret key, panel state
CONFIG_JSON = ROOT / "config.json"
CA_DIR = ROOT / "ca"
REQUIREMENTS = ROOT / "requirements.txt"
BACKUP_DIR = ROOT / "backups"

DEFAULT_PORT = 8600
DEFAULT_HOST = "127.0.0.1"

# PBKDF2 parameters — must match engine/account_manager.py so a password set
# here verifies in the panel. Replicated rather than imported so the manager
# needs no dependencies.
PBKDF2_ITERATIONS = 120_000
SALT_BYTES = 16


# ── colour ─────────────────────────────────────────────────────────────
def _supports_colour() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if IS_WINDOWS:
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)   # ENABLE_VIRTUAL_TERMINAL
            return True
        except Exception:
            return False
    return True


_C = _supports_colour()


def c(code: str, text) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if _C else str(text)


def bold(t):  return c("1", t)
def dim(t):   return c("2", t)
def red(t):   return c("31", t)
def green(t): return c("32", t)
def yellow(t): return c("33", t)
def blue(t):  return c("36", t)
def purple(t): return c("35", t)


# ── small helpers ──────────────────────────────────────────────────────
def read_version() -> str:
    try:
        text = (ROOT / "panel" / "__init__.py").read_text(encoding="utf-8")
        m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "?"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    _chmod_600(STATE_FILE)


def panel_port() -> int:
    try:
        return int(load_state().get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        return DEFAULT_PORT


def panel_host() -> str:
    return str(load_state().get("host", DEFAULT_HOST)) or DEFAULT_HOST


def _chmod_600(path: Path) -> None:
    if not IS_WINDOWS:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def have_git() -> bool:
    return shutil.which("git") is not None and (ROOT / ".git").is_dir()


def find_system_python() -> str | None:
    for name in ("python3.13", "python3.12", "python3.11", "python3.10",
                 "python3", "python"):
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            out = subprocess.run([exe, "-c",
                                  "import sys;print('%d.%d'%sys.version_info[:2])"],
                                 capture_output=True, text=True, timeout=10)
            major, _, minor = out.stdout.strip().partition(".")
            if major.isdigit() and minor.isdigit() and (int(major), int(minor)) >= (3, 10):
                return exe
        except Exception:
            continue
    return None


def venv_ready() -> bool:
    return VENV_PY.exists()


# ── process control ────────────────────────────────────────────────────
def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    if IS_WINDOWS:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True)
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    probe = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    try:
        with socket.create_connection((probe, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_running() -> bool:
    """True when the panel actually answers on its port, not merely that a PID
    file exists — a stale PID after a reboot must not read as Running."""
    if _port_open(panel_host(), panel_port()):
        return True
    pid = _read_pid()
    return _pid_alive(pid) and _port_open(panel_host(), panel_port(), 0.3)


def start_panel(quiet: bool = False) -> bool:
    if not venv_ready():
        print(red("  Not installed yet — run Install (1) first."))
        return False
    if is_running():
        if not quiet:
            print(yellow("  Panel is already running."))
        return True

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ARAS_PANEL_PORT"] = str(panel_port())
    env["ARAS_PANEL_HOST"] = panel_host()
    log = open(LOG_FILE, "ab")
    try:
        if IS_WINDOWS:
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
            proc = subprocess.Popen(
                [str(VENV_PY), "-m", "panel"], cwd=str(ROOT), env=env,
                stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                creationflags=flags, close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                [str(VENV_PY), "-m", "panel"], cwd=str(ROOT), env=env,
                stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                start_new_session=True, close_fds=True,
            )
    finally:
        log.close()

    PID_FILE.write_text(str(proc.pid))
    _chmod_600(PID_FILE)

    for _ in range(20):
        if _port_open(panel_host(), panel_port(), 0.4):
            if not quiet:
                print(green(f"  Panel is up  ->  http://{panel_host()}:{panel_port()}"))
            return True
        if proc.poll() is not None:
            break
        time.sleep(0.5)

    print(red("  Panel failed to start. Last log lines:"))
    _tail(LOG_FILE, 20)
    return False


def stop_panel(quiet: bool = False) -> bool:
    pid = _read_pid()
    if not is_running():
        if not quiet:
            print(yellow("  Panel is not running."))
        PID_FILE.unlink(missing_ok=True)
        return True
    if pid is None:
        if not quiet:
            print(yellow("  Panel port is open but PID unknown — cannot stop safely."))
        return False
    if IS_WINDOWS:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        for _ in range(20):
            if not _pid_alive(pid):
                break
            time.sleep(0.3)
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    PID_FILE.unlink(missing_ok=True)
    if not quiet:
        print(green("  Panel stopped."))
    return True


def _tail(path: Path, n: int) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        print(dim("  No log yet."))
        return
    for line in lines[-n:]:
        print("   " + line)


# ── pip / git actions ──────────────────────────────────────────────────
def _run(cmd: list[str], **kw) -> int:
    print(dim("  $ " + " ".join(cmd)))
    try:
        return subprocess.call(cmd, cwd=str(ROOT), **kw)
    except FileNotFoundError as exc:
        print(red(f"  Command not found: {exc}"))
        return 127


def install_deps() -> bool:
    if not venv_ready():
        py = find_system_python()
        if not py:
            print(red("  Python 3.10+ not found. Install it first."))
            return False
        print(blue("  Creating the virtualenv (.venv)..."))
        if _run([py, "-m", "venv", str(VENV_DIR)]) != 0:
            print(red("  Failed to create the virtualenv."))
            return False
    print(blue("  Installing / updating dependencies..."))
    _run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check",
          "-q", "--upgrade", "pip"])
    rc = _run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check",
               "-q", "-r", str(REQUIREMENTS)])
    if rc != 0:
        print(red("  Dependency install failed. Check your connection."))
        return False
    print(green("  Ready."))
    return True


def action_install() -> None:
    _header("Install")
    if venv_ready():
        print(yellow("  Environment already exists; just updating dependencies."))
    if not install_deps():
        return
    # Create the global command right away, without asking — the whole point
    # of the manager is to be reachable as `agp` from anywhere; asking every
    # time only adds a step to the setup people actually want.
    if not IS_WINDOWS:
        _install_global_command()
    if _confirm("Start the panel now?", default=True):
        start_panel()


def action_update() -> None:
    _header("Update")
    was_running = is_running()
    if have_git():
        print(blue("  Pulling the latest version from GitHub..."))
        _run(["git", "fetch", "--tags", "--quiet"])
        if _run(["git", "pull", "--ff-only"]) != 0:
            print(yellow("  Fast-forward pull failed — you may have local changes."))
            print(yellow("  Resolve it by hand, or use 'Specific version' instead."))
    else:
        print(yellow("  Git is not active here. To update, clone/download again."))
        return
    install_deps()
    print(green(f"  You are now on version {read_version()}."))
    if was_running and _confirm("Restart the panel?", default=True):
        stop_panel(quiet=True)
        start_panel()


def action_legacy_version() -> None:
    _header("Use a specific version")
    if not have_git():
        print(yellow("  This needs git (a git clone, not a zip download)."))
        return
    tags = subprocess.run(["git", "tag", "--sort=-v:refname"],
                          cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    if tags:
        print("  Available versions:")
        for t in tags[:15]:
            print("   - " + t)
    target = _ask("Version or tag (empty = cancel)").strip()
    if not target:
        return
    was_running = is_running()
    if _run(["git", "checkout", target]) != 0:
        print(red("  That version was not found."))
        return
    install_deps()
    print(green(f"  You are now on {read_version()}."))
    print(dim("  Back to latest: the 'Update' item, or 'git checkout main'."))
    if was_running and _confirm("Restart the panel?", default=True):
        stop_panel(quiet=True)
        start_panel()


def action_uninstall() -> None:
    _header("Uninstall")
    print(red("  This stops the panel and removes the virtualenv and autostart."))
    if not _confirm("Are you sure?", default=False):
        return
    stop_panel(quiet=True)
    _disable_autostart(quiet=True)
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)
        print(green("  Virtualenv removed."))
    print()
    print(yellow("  Your data (config.json, ca/, panel password, relays) is still here."))
    if _confirm("Delete that data too, permanently?", default=False):
        for p in (CONFIG_JSON, DATA_DIR, ROOT / "ca"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        print(green("  Everything wiped."))
    print(dim("  Source files are untouched; delete the folder to remove fully."))


# ── settings actions ───────────────────────────────────────────────────
def action_change_port() -> None:
    _header("Change panel port")
    print(f"  Current port: {bold(panel_port())}")
    raw = _ask("New port (1024-65535)").strip()
    if not raw:
        return
    try:
        port = int(raw)
        if not (1024 <= port <= 65535):
            raise ValueError
    except ValueError:
        print(red("  Invalid port."))
        return
    if port != panel_port() and _port_open("127.0.0.1", port):
        print(red(f"  Port {port} is already in use. Pick another."))
        return
    state = load_state()
    state["port"] = port
    save_state(state)
    print(green(f"  Port set to {port}."))
    if is_running():
        if _confirm("Restart the panel to apply?", default=True):
            stop_panel(quiet=True)
            start_panel()
    if _autostart_installed():
        _enable_autostart(quiet=True)   # rewrite service with the new port


def action_change_password() -> None:
    _header("Change panel password")
    print(dim("  This is the login password for the panel (not proxy users)."))
    pw1 = _ask_secret("New password (min 10 chars)")
    if pw1 is None:
        return
    if len(pw1) < 10:
        print(red("  Password must be at least 10 characters."))
        return
    pw2 = _ask_secret("Repeat password")
    if pw2 is None:
        return
    if pw2 != pw1:
        print(red("  Passwords do not match."))
        return
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", pw1.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    record = {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
        "iterations": PBKDF2_ITERATIONS,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        state = json.loads(PANEL_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    state["admin"] = record
    PANEL_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    _chmod_600(PANEL_JSON)
    print(green("  Panel password changed."))
    if is_running():
        print(dim("  Any open sessions will have to log in again."))


def action_view_settings() -> None:
    _header("Current settings")
    v = read_version()
    print(f"  Panel version   : {bold(v)}")
    print(f"  Panel URL       : http://{panel_host()}:{panel_port()}")
    print(f"  State           : "
          + (green("running") if is_running() else red("stopped")))
    print(f"  Autostart       : "
          + (green("on") if _autostart_installed() else dim("off")))
    print(f"  Virtualenv      : "
          + (green("installed") if venv_ready() else red("not installed")))
    print(f"  Panel password  : "
          + (green("set") if _admin_set() else yellow("not set yet")))
    print(dim("  -- relay config --"))
    cfg = _load_json(CONFIG_JSON)
    if not cfg:
        print(dim("    No relay config yet (config.json missing)."))
    else:
        print(f"    HTTP proxy port : {cfg.get('listen_port', '-')}")
        print(f"    SOCKS5 port     : {cfg.get('socks5_port', '-')}")
        print(f"    Front domain    : {cfg.get('front_domain', '-')}")
        sid = cfg.get("script_id") or cfg.get("script_ids") or "-"
        if isinstance(sid, list):
            sid = f"{len(sid)} scripts"
        print(f"    Apps Script     : {_short(str(sid))}")
        print(f"    Auth key        : "
              + (green("auto (set)") if cfg.get("auth_key") else yellow("empty")))
    pj = _load_json(PANEL_JSON)
    worker = ((pj.get("cloudflare") or {}).get("worker_url")) if pj else ""
    print(f"    Cloudflare Worker: {worker or dim('-')}")


def action_logs() -> None:
    _header("Live log")
    if not LOG_FILE.exists():
        print(dim("  No log yet."))
        return
    print(dim("  Last 40 lines (to follow live, run this in a terminal:"))
    print(dim(f"    tail -f {LOG_FILE})"))
    print()
    _tail(LOG_FILE, 40)


# ── autostart (per-OS) ─────────────────────────────────────────────────
SYSTEMD_UNIT = Path("/etc/systemd/system/aras-panel.service")
LAUNCHD_PLIST = Path.home() / "Library/LaunchAgents/com.aras-gp.panel.plist"
WIN_TASK = "Aras-GP-Panel"


def _autostart_installed() -> bool:
    if IS_WINDOWS:
        out = subprocess.run(["schtasks", "/query", "/tn", WIN_TASK],
                             capture_output=True, text=True)
        return out.returncode == 0
    if IS_MAC:
        return LAUNCHD_PLIST.exists()
    return SYSTEMD_UNIT.exists()


def _enable_autostart(quiet: bool = False) -> None:
    port, host = panel_port(), panel_host()
    if IS_WINDOWS:
        cmd = f'"{VENV_PY}" -m panel'
        subprocess.run(["schtasks", "/create", "/tn", WIN_TASK, "/sc", "onlogon",
                        "/rl", "highest", "/f", "/tr",
                        f'cmd /c "cd /d {ROOT} && set ARAS_PANEL_PORT={port} && {cmd}"'],
                       capture_output=True)
    elif IS_MAC:
        LAUNCHD_PLIST.parent.mkdir(parents=True, exist_ok=True)
        LAUNCHD_PLIST.write_text(_launchd_plist(port, host), encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)],
                       capture_output=True)
        subprocess.run(["launchctl", "load", str(LAUNCHD_PLIST)],
                       capture_output=True)
    else:
        if os.geteuid() != 0:
            print(yellow("  Autostart on Linux (systemd) needs sudo:"))
            print(dim(f"    sudo {sys.executable} {__file__}   then the autostart item"))
            return
        SYSTEMD_UNIT.write_text(_systemd_unit(port, host), encoding="utf-8")
        subprocess.run(["systemctl", "daemon-reload"])
        subprocess.run(["systemctl", "enable", "--now", "aras-panel"])
    if not quiet:
        print(green("  Autostart enabled — the panel starts with the system."))


def _disable_autostart(quiet: bool = False) -> None:
    if IS_WINDOWS:
        subprocess.run(["schtasks", "/delete", "/tn", WIN_TASK, "/f"],
                       capture_output=True)
    elif IS_MAC:
        if LAUNCHD_PLIST.exists():
            subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)],
                           capture_output=True)
            LAUNCHD_PLIST.unlink(missing_ok=True)
    else:
        if SYSTEMD_UNIT.exists():
            if os.geteuid() != 0:
                print(yellow("  Disabling systemd autostart needs sudo."))
                return
            subprocess.run(["systemctl", "disable", "--now", "aras-panel"])
            SYSTEMD_UNIT.unlink(missing_ok=True)
            subprocess.run(["systemctl", "daemon-reload"])
    if not quiet:
        print(green("  Autostart disabled."))


def _systemd_unit(port: int, host: str) -> str:
    return (
        "[Unit]\n"
        "Description=Aras-GP Panel\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={ROOT}\n"
        f"Environment=ARAS_PANEL_PORT={port}\n"
        f"Environment=ARAS_PANEL_HOST={host}\n"
        f"ExecStart={VENV_PY} -m panel\n"
        "Restart=on-failure\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _launchd_plist(port: int, host: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        '  <key>Label</key><string>com.aras-gp.panel</string>\n'
        '  <key>ProgramArguments</key>\n'
        f'  <array><string>{VENV_PY}</string><string>-m</string>\n'
        '  <string>panel</string></array>\n'
        f'  <key>WorkingDirectory</key><string>{ROOT}</string>\n'
        '  <key>EnvironmentVariables</key><dict>\n'
        f'    <key>ARAS_PANEL_PORT</key><string>{port}</string>\n'
        f'    <key>ARAS_PANEL_HOST</key><string>{host}</string>\n'
        '  </dict>\n'
        '  <key>RunAtLoad</key><true/>\n'
        '  <key>KeepAlive</key><true/>\n'
        f'  <key>StandardOutPath</key><string>{LOG_FILE}</string>\n'
        f'  <key>StandardErrorPath</key><string>{LOG_FILE}</string>\n'
        '</dict></plist>\n'
    )


def action_enable_autostart() -> None:
    _header("Enable autostart")
    _enable_autostart()


def action_disable_autostart() -> None:
    _header("Disable autostart")
    _disable_autostart()


def _install_global_command() -> None:
    wrapper = f'#!/usr/bin/env bash\nexec "{sys.executable}" "{__file__}" "$@"\n'
    path_dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]

    # Prefer a directory that is already on PATH *and* writable, so `agp` works
    # in the same shell with no profile edit — as root on a VPS that is
    # /usr/local/bin or /usr/bin, on a Homebrew Mac /opt/homebrew/bin.
    on_path = [d for d in path_dirs
               if os.path.isdir(d) and os.access(d, os.W_OK)]
    fallback = str(Path.home() / ".local/bin")
    for d in on_path + [fallback]:
        dst = Path(d) / "agp"
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
            dst.write_text(wrapper, encoding="utf-8")
            os.chmod(dst, 0o755)
            print(green(f"  Global 'agp' command created: {dst}"))
            if d in path_dirs:
                print(dim("  Now just type  agp  from anywhere to open this menu."))
            else:
                print(yellow(f"  {d} is not on your PATH yet. Add it:"))
                print(dim(f'    echo \'export PATH="{d}:$PATH"\' >> ~/.bashrc'))
                print(dim("  (or ~/.zshrc on macOS), then open a new terminal."))
            return
        except OSError:
            continue
    print(yellow("  Could not create a global command (no permission). "
                 "Run it with ./agp.sh instead."))


# ── backup / export / import / reset ───────────────────────────────────
# Everything that a re-clone destroys and cannot be regenerated: the relay
# config, the panel state (password, saved Cloudflare token, relays, friends),
# and the CA the browser trusts. One archive captures all three.
def _backup_map() -> list[tuple[Path, str]]:
    return [
        (CONFIG_JSON, "config.json"),
        (DATA_DIR, "panel-data"),
        (CA_DIR, "ca"),
    ]


def create_backup(dest_dir: Path | None = None) -> tuple[Path, int]:
    dest = Path(dest_dir) if dest_dir else BACKUP_DIR
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = dest / f"aras-backup-{stamp}.tar.gz"
    added = 0
    with tarfile.open(path, "w:gz") as tar:
        for src, arc in _backup_map():
            if src.exists():
                tar.add(str(src), arcname=arc)
                added += 1
    _chmod_600(path)
    return path, added


def _restore_target(name: str) -> Path | None:
    """Map an archive member to where it belongs, or None to skip.

    Membership is decided by fixed top-level names, and anything absolute or
    containing ``..`` is refused — a backup is normally self-made, but a
    restore must never write outside the project even if the file was tampered
    with."""
    name = name.replace("\\", "/").strip("/")
    if not name or ".." in name.split("/"):
        return None
    if name == "config.json":
        return CONFIG_JSON
    if name == "panel-data" or name.startswith("panel-data/"):
        rel = name[len("panel-data"):].strip("/")
        return DATA_DIR / rel if rel else DATA_DIR
    if name == "ca" or name.startswith("ca/"):
        rel = name[len("ca"):].strip("/")
        return CA_DIR / rel if rel else CA_DIR
    return None


def restore_backup(path: Path) -> int:
    restored = 0
    with tarfile.open(str(path), "r:gz") as tar:
        for member in tar.getmembers():
            target = _restore_target(member.name)
            if target is None:
                continue
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                with extracted, open(target, "wb") as out:
                    shutil.copyfileobj(extracted, out)
                if target.name in ("ca.key", "panel.json", "config.json"):
                    _chmod_600(target)
                restored += 1
    return restored


def list_backups() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("aras-backup-*.tar.gz"), reverse=True)


def action_backup() -> None:
    _header("Backup")
    try:
        path, n = create_backup()
    except OSError as exc:
        print(red(f"  Backup failed: {exc}"))
        return
    size = path.stat().st_size
    print(green(f"  Backup created ({n} parts, {size // 1024} KB):"))
    print("   " + str(path))
    print(yellow("  It holds secrets and keys — keep it safe (mode 0600)."))
    print(dim("  To move it to another server: use Export, or scp it directly."))


def action_export() -> None:
    _header("Export backup to a path")
    raw = _ask("Destination folder (empty = your home dir)").strip()
    dest = Path(os.path.expanduser(raw)) if raw else Path.home()
    if not dest.is_dir():
        print(red(f"  Folder not found: {dest}"))
        return
    try:
        path, n = create_backup(dest)
    except OSError as exc:
        print(red(f"  Failed: {exc}"))
        return
    print(green(f"  Exported to: {path}"))


def action_import() -> None:
    _header("Restore from backup")
    backups = list_backups()
    chosen: Path | None = None
    if backups:
        print("  Available backups:")
        for i, b in enumerate(backups[:10], 1):
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(b.stat().st_mtime))
            print(f"   {i}. {b.name}  ({when})")
        pick = _ask("Backup number, or a file path (empty = cancel)").strip()
        if not pick:
            return
        if pick.isdigit() and 1 <= int(pick) <= len(backups[:10]):
            chosen = backups[int(pick) - 1]
        else:
            chosen = Path(os.path.expanduser(pick))
    else:
        pick = _ask("Path to a backup file (.tar.gz)").strip()
        if not pick:
            return
        chosen = Path(os.path.expanduser(pick))

    if not chosen or not chosen.exists():
        print(red("  Backup file not found."))
        return
    print(yellow(f"  '{chosen.name}' will overwrite your current data."))
    if not _confirm("Continue?", default=False):
        return
    was_running = is_running()
    if was_running:
        stop_panel(quiet=True)
    try:
        n = restore_backup(chosen)
    except (OSError, tarfile.TarError) as exc:
        print(red(f"  Restore failed: {exc}"))
        return
    print(green(f"  Restored ({n} files)."))
    if was_running and _confirm("Restart the panel?", default=True):
        start_panel()


def action_reset() -> None:
    _header("Reset to factory")
    print(red("  This wipes the panel password, Cloudflare token, saved relays and friends."))
    print(dim("  The CA certificate and the source files are left alone."))
    if not _confirm("Are you sure? (tip: take a backup first)", default=False):
        return
    if is_running():
        stop_panel(quiet=True)
    try:
        if PANEL_JSON.exists():
            PANEL_JSON.unlink()
        profiles = DATA_DIR / "profiles"
        if profiles.is_dir():
            shutil.rmtree(profiles, ignore_errors=True)
        if _confirm("Delete the relay config (config.json) too?", default=False):
            CONFIG_JSON.unlink(missing_ok=True)
    except OSError as exc:
        print(red(f"  Error: {exc}"))
        return
    print(green("  Reset done. Next start, the panel shows first-run setup."))


# ── panel host (LAN access) ────────────────────────────────────────────
def action_toggle_lan() -> None:
    _header("LAN access")
    host = panel_host()
    on_lan = host not in ("127.0.0.1", "localhost", "::1")
    if on_lan:
        print(f"  The panel is on {bold(host)} now (reachable from the network).")
        if _confirm("Switch back to this device only (127.0.0.1)?", default=True):
            _set_host("127.0.0.1")
        return
    print("  The panel is on this device only (127.0.0.1) now.")
    print(yellow("  Warning: opening it to the network lets anyone on that network"))
    print(yellow("  reach the panel. It holds your password and Cloudflare token —"))
    print(yellow("  set a strong panel password first."))
    if _confirm("Open it to the whole network (reach it from a phone)?", default=False):
        _set_host("0.0.0.0")
        print(dim(f"  From a phone: http://<this device's IP>:{panel_port()}"))


def _set_host(host: str) -> None:
    state = load_state()
    state["host"] = host
    save_state(state)
    print(green(f"  Set to {host}."))
    if is_running() and _confirm("Restart the panel to apply?", default=True):
        stop_panel(quiet=True)
        start_panel()
    if _autostart_installed():
        _enable_autostart(quiet=True)


def action_open_browser() -> None:
    _header("Open the panel in a browser")
    url = f"http://{('127.0.0.1' if panel_host() in ('0.0.0.0', '::') else panel_host())}:{panel_port()}"
    if not is_running():
        print(yellow("  The panel is off; start it first (item 5)."))
    print("  " + bold(url))
    try:
        if webbrowser.open(url):
            print(green("  Opened in your browser."))
        else:
            print(dim("  No browser found (headless server?) — open the URL above."))
    except Exception:
        print(dim("  Could not open it automatically — open the URL above."))


# ── input helpers ──────────────────────────────────────────────────────
def _ask(prompt: str) -> str:
    try:
        return input(blue("  > ") + prompt + ": ")
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _ask_secret(prompt: str) -> str | None:
    try:
        return getpass.getpass(f"  > {prompt}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _confirm(prompt: str, default: bool = False) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    ans = _ask(f"{prompt} {hint}").strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _admin_set() -> bool:
    return bool((_load_json(PANEL_JSON).get("admin") or {}).get("hash"))


def _short(text: str, keep: int = 22) -> str:
    return text if len(text) <= keep else text[:keep] + "..."


def _header(title: str) -> None:
    print()
    print(purple("  -- " + title + " --"))


# ── menu ───────────────────────────────────────────────────────────────
_W = 46


def _line() -> str:
    return "|" + "-" * _W + "|"


def _row(text: str) -> str:
    visible = re.sub(r"\x1b\[[0-9;]*m", "", text)   # measure without ANSI
    pad = _W - 2 - len(visible)
    return "|  " + text + " " * max(0, pad) + "|"


# Data-driven so the box, the numbering and the dispatch table can never drift
# apart: one list is the whole menu. "-" is a section rule.
MENU: list = [
    ("1", "Install"),
    ("2", "Update"),
    ("3", "Use a specific version (legacy)"),
    ("4", "Uninstall"),
    "-",
    ("5", "Start"),
    ("6", "Stop"),
    ("7", "Restart"),
    ("8", "Status"),
    ("9", "Logs"),
    "-",
    ("10", "Change panel port"),
    ("11", "Change panel password"),
    ("12", "LAN access (localhost / network)"),
    ("13", "View settings"),
    "-",
    ("14", "Backup"),
    ("15", "Export backup to a path"),
    ("16", "Restore from backup"),
    ("17", "Reset to factory"),
    "-",
    ("18", "Enable autostart"),
    ("19", "Disable autostart"),
    "-",
    ("20", "Open the panel in a browser"),
]

ACTIONS = {
    "1": action_install,
    "2": action_update,
    "3": action_legacy_version,
    "4": action_uninstall,
    "5": lambda: start_panel(),
    "6": lambda: stop_panel(),
    "7": lambda: (stop_panel(quiet=True), start_panel()),
    "8": action_view_settings,
    "9": action_logs,
    "10": action_change_port,
    "11": action_change_password,
    "12": action_toggle_lan,
    "13": action_view_settings,
    "14": action_backup,
    "15": action_export,
    "16": action_import,
    "17": action_reset,
    "18": action_enable_autostart,
    "19": action_disable_autostart,
    "20": action_open_browser,
}

_MAX_CHOICE = max(int(k) for k in ACTIONS)


def draw_menu() -> None:
    running = is_running()
    v = read_version()
    state_txt = green("running") if running else red("stopped")
    auto_txt = green("on") if _autostart_installed() else "off"

    print()
    print(blue("+" + "-" * _W + "+"))
    print(blue(_row(bold("Aras-GP  -  Panel Manager") + dim(f"   v{v}"))))
    print(blue(_line()))
    print(blue(_row("0. Exit")))
    print(blue(_line()))
    for item in MENU:
        if item == "-":
            print(blue(_line()))
        else:
            num, label = item
            print(blue(_row(f"{num}. {label}")))
    print(blue("+" + "-" * _W + "+"))
    url = f"http://{panel_host()}:{panel_port()}"
    print(f"  Panel     : {state_txt}" + (dim("   " + url) if running else ""))
    print(f"  Autostart : {auto_txt}")


def menu_loop() -> None:
    while True:
        draw_menu()
        try:
            choice = input(blue("  > ") + f"Select [0-{_MAX_CHOICE}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            # A closed or piped-empty stdin must end the menu, not spin on it.
            print()
            return
        if choice in ("0", "q", "exit", "quit"):
            print(dim("  Bye."))
            return
        action = ACTIONS.get(choice)
        if not action:
            print(red("  Invalid choice."))
            continue
        try:
            action()
        except KeyboardInterrupt:
            print()
        except Exception as exc:      # never let one action crash the menu
            print(red(f"  Error: {exc}"))
        _ask("Press Enter to continue")


# ── non-interactive CLI (for services and scripting) ───────────────────
def cli(argv: list[str]) -> int:
    cmd = argv[0].lower()
    table = {
        "start": lambda: 0 if start_panel() else 1,
        "stop": lambda: 0 if stop_panel() else 1,
        "restart": lambda: (stop_panel(quiet=True), 0 if start_panel() else 1)[1],
        "status": lambda: (print("running" if is_running() else "stopped"),
                           0 if is_running() else 1)[1],
        "install": lambda: 0 if install_deps() else 1,
        "version": lambda: (print(read_version()), 0)[1],
    }
    fn = table.get(cmd)
    if not fn:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print("commands: start stop restart status install version", file=sys.stderr)
        return 2
    return fn()


def main() -> int:
    if len(sys.argv) > 1:
        return cli(sys.argv[1:])
    try:
        menu_loop()
    except KeyboardInterrupt:
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
