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

Run it with `python3 manage.py`, or through the `aras.sh` / `aras.bat` wrappers,
or — after Install offers it — the global `aras` command.
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
import time
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
REQUIREMENTS = ROOT / "requirements.txt"

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


def _pid_alive(pid: int) -> bool:
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
        print(red("  محیط نصب نشده — اول گزینه‌ی «نصب» (۱) را بزنید."))
        return False
    if is_running():
        if not quiet:
            print(yellow("  پنل از قبل در حال اجراست."))
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
                print(green(f"  پنل بالا آمد → http://{panel_host()}:{panel_port()}"))
            return True
        if proc.poll() is not None:
            break
        time.sleep(0.5)

    print(red("  پنل بالا نیامد. آخرین خطوط لاگ:"))
    _tail(LOG_FILE, 20)
    return False


def stop_panel(quiet: bool = False) -> bool:
    pid = _read_pid()
    if not _pid_alive(pid) and not is_running():
        if not quiet:
            print(yellow("  پنل در حال اجرا نیست."))
        PID_FILE.unlink(missing_ok=True)
        return True
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
        print(green("  پنل متوقف شد."))
    return True


def _tail(path: Path, n: int) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        print(dim("  لاگی موجود نیست."))
        return
    for line in lines[-n:]:
        print("   " + line)


# ── pip / git actions ──────────────────────────────────────────────────
def _run(cmd: list[str], **kw) -> int:
    print(dim("  $ " + " ".join(cmd)))
    try:
        return subprocess.call(cmd, cwd=str(ROOT), **kw)
    except FileNotFoundError as exc:
        print(red(f"  دستور پیدا نشد: {exc}"))
        return 127


def install_deps() -> bool:
    if not venv_ready():
        py = find_system_python()
        if not py:
            print(red("  پایتون ۳٫۱۰ به بالا پیدا نشد. اول نصبش کنید."))
            return False
        print(blue("  ساخت محیط مجازی (.venv)…"))
        if _run([py, "-m", "venv", str(VENV_DIR)]) != 0:
            print(red("  ساخت venv ناموفق بود."))
            return False
    print(blue("  نصب/به‌روزرسانی وابستگی‌ها…"))
    _run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check",
          "-q", "--upgrade", "pip"])
    rc = _run([str(VENV_PY), "-m", "pip", "install", "--disable-pip-version-check",
               "-q", "-r", str(REQUIREMENTS)])
    if rc != 0:
        print(red("  نصب وابستگی‌ها ناموفق بود. اینترنت/فیلترینگ را بررسی کنید."))
        return False
    print(green("  آماده شد."))
    return True


def action_install() -> None:
    _header("نصب")
    if venv_ready():
        print(yellow("  محیط از قبل وجود دارد؛ فقط وابستگی‌ها به‌روز می‌شوند."))
    if not install_deps():
        return
    if _confirm("پنل همین حالا روشن شود؟", default=True):
        start_panel()
    if not IS_WINDOWS and _confirm("دستور سراسری «aras» ساخته شود تا از هرجا اجرا شود؟",
                                   default=True):
        _install_global_command()


def action_update() -> None:
    _header("به‌روزرسانی")
    was_running = is_running()
    if have_git():
        print(blue("  گرفتن آخرین نسخه از گیت‌هاب…"))
        _run(["git", "fetch", "--tags", "--quiet"])
        if _run(["git", "pull", "--ff-only"]) != 0:
            print(yellow("  pull با fast-forward نشد — شاید تغییرات محلی دارید."))
            print(yellow("  دستی حلش کنید یا از «نسخه‌ی مشخص» استفاده کنید."))
    else:
        print(yellow("  گیت روی این پوشه فعال نیست. برای آپدیت، دوباره کلون/دانلود کنید."))
        return
    install_deps()
    print(green(f"  اکنون روی نسخه‌ی {read_version()} هستید."))
    if was_running and _confirm("پنل دوباره راه‌اندازی شود؟", default=True):
        stop_panel(quiet=True)
        start_panel()


def action_legacy_version() -> None:
    _header("استفاده از نسخه‌ی مشخص")
    if not have_git():
        print(yellow("  برای این کار گیت لازم است (کلون گیت، نه دانلود zip)."))
        return
    tags = subprocess.run(["git", "tag", "--sort=-v:refname"],
                          cwd=str(ROOT), capture_output=True, text=True).stdout.split()
    if tags:
        print("  نسخه‌های موجود:")
        for t in tags[:15]:
            print("   • " + t)
    target = _ask("نسخه یا تگ (خالی = انصراف)").strip()
    if not target:
        return
    was_running = is_running()
    if _run(["git", "checkout", target]) != 0:
        print(red("  آن نسخه پیدا نشد."))
        return
    install_deps()
    print(green(f"  اکنون روی {read_version()} هستید."))
    print(dim("  برای بازگشت به آخرین نسخه: گزینه‌ی «به‌روزرسانی» یا «git checkout main»."))
    if was_running and _confirm("پنل دوباره راه‌اندازی شود؟", default=True):
        stop_panel(quiet=True)
        start_panel()


def action_uninstall() -> None:
    _header("حذف")
    print(red("  این کار پنل را متوقف و محیط مجازی و اتواستارت را حذف می‌کند."))
    if not _confirm("مطمئنید؟", default=False):
        return
    stop_panel(quiet=True)
    _disable_autostart(quiet=True)
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR, ignore_errors=True)
        print(green("  محیط مجازی حذف شد."))
    print()
    print(yellow("  داده‌های شما (config.json، ca/، رمز پنل، رله‌ها) هنوز سر جایشان هستند."))
    if _confirm("این داده‌ها هم برای همیشه پاک شوند؟", default=False):
        for p in (CONFIG_JSON, DATA_DIR, ROOT / "ca"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        print(green("  همه‌چیز پاک شد."))
    print(dim("  فایل‌های سورس دست‌نخورده‌اند؛ برای حذف کامل، پوشه را پاک کنید."))


# ── settings actions ───────────────────────────────────────────────────
def action_change_port() -> None:
    _header("تغییر پورت پنل")
    print(f"  پورت فعلی: {bold(panel_port())}")
    raw = _ask("پورت جدید (۱۰۲۴ تا ۶۵۵۳۵)").strip()
    if not raw:
        return
    try:
        port = int(raw)
        if not (1024 <= port <= 65535):
            raise ValueError
    except ValueError:
        print(red("  پورت نامعتبر."))
        return
    if port != panel_port() and _port_open("127.0.0.1", port):
        print(red(f"  پورت {port} همین حالا اشغال است. یکی دیگر انتخاب کنید."))
        return
    state = load_state()
    state["port"] = port
    save_state(state)
    print(green(f"  پورت روی {port} تنظیم شد."))
    if is_running():
        if _confirm("برای اعمال، پنل ری‌استارت شود؟", default=True):
            stop_panel(quiet=True)
            start_panel()
    if _autostart_installed():
        _enable_autostart(quiet=True)   # rewrite service with the new port


def action_change_password() -> None:
    _header("تغییر رمز پنل")
    print(dim("  این رمز، رمز ورود به خود پنل است (نه رمز کاربران پروکسی)."))
    pw1 = _ask_secret("رمز جدید (حداقل ۱۰ کاراکتر)")
    if pw1 is None:
        return
    if len(pw1) < 10:
        print(red("  رمز باید حداقل ۱۰ کاراکتر باشد."))
        return
    pw2 = _ask_secret("تکرار رمز")
    if pw2 != pw1:
        print(red("  دو رمز یکسان نیستند."))
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
    print(green("  رمز پنل تغییر کرد."))
    if is_running():
        print(dim("  همه‌ی نشست‌های باز باید دوباره وارد شوند."))


def action_view_settings() -> None:
    _header("تنظیمات فعلی")
    v = read_version()
    print(f"  نسخه‌ی پنل        : {bold(v)}")
    print(f"  آدرس پنل         : http://{panel_host()}:{panel_port()}")
    print(f"  وضعیت            : "
          + (green("در حال اجرا") if is_running() else red("متوقف")))
    print(f"  اتواستارت        : "
          + (green("روشن") if _autostart_installed() else dim("خاموش")))
    print(f"  محیط مجازی       : "
          + (green("نصب‌شده") if venv_ready() else red("نصب نشده")))
    print(f"  رمز پنل          : "
          + (green("تنظیم‌شده") if _admin_set() else yellow("هنوز تنظیم نشده")))
    print(dim("  ── کانفیگ رله ──"))
    cfg = _load_json(CONFIG_JSON)
    if not cfg:
        print(dim("    هنوز کانفیگ رله ساخته نشده (config.json نیست)."))
    else:
        print(f"    پورت HTTP proxy : {cfg.get('listen_port', '—')}")
        print(f"    پورت SOCKS5     : {cfg.get('socks5_port', '—')}")
        print(f"    دامنه‌ی فرانت    : {cfg.get('front_domain', '—')}")
        sid = cfg.get("script_id") or cfg.get("script_ids") or "—"
        if isinstance(sid, list):
            sid = f"{len(sid)} اسکریپت"
        print(f"    Apps Script     : {_short(str(sid))}")
        print(f"    کلید auth       : "
              + (green("خودکار (تنظیم‌شده)") if cfg.get("auth_key") else yellow("خالی")))
    pj = _load_json(PANEL_JSON)
    worker = ((pj.get("cloudflare") or {}).get("worker_url")) if pj else ""
    print(f"    Cloudflare Worker: {worker or dim('—')}")


def action_logs() -> None:
    _header("لاگ زنده")
    if not LOG_FILE.exists():
        print(dim("  هنوز لاگی نیست."))
        return
    print(dim("  آخرین ۴۰ خط (برای دنبال‌کردن زنده، این را در ترمینال بزنید:"))
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
                        f'cmd /c "cd /d {ROOT} && set ARAS_PANEL_PORT={port}&& {cmd}"'],
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
            print(yellow("  برای اتواستارت روی لینوکس (systemd) به sudo نیاز است:"))
            print(dim(f"    sudo {sys.executable} {__file__}  → سپس گزینه‌ی اتواستارت"))
            return
        SYSTEMD_UNIT.write_text(_systemd_unit(port, host), encoding="utf-8")
        subprocess.run(["systemctl", "daemon-reload"])
        subprocess.run(["systemctl", "enable", "--now", "aras-panel"])
    if not quiet:
        print(green("  اتواستارت روشن شد — پنل با روشن‌شدن سیستم بالا می‌آید."))


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
                print(yellow("  برای خاموش‌کردن اتواستارت systemd به sudo نیاز است."))
                return
            subprocess.run(["systemctl", "disable", "--now", "aras-panel"])
            SYSTEMD_UNIT.unlink(missing_ok=True)
            subprocess.run(["systemctl", "daemon-reload"])
    if not quiet:
        print(green("  اتواستارت خاموش شد."))


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
        f'  <array><string>{VENV_PY}</string><string>-m</string>'
        '<string>panel</string></array>\n'
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
    _header("روشن‌کردن اتواستارت")
    _enable_autostart()


def action_disable_autostart() -> None:
    _header("خاموش‌کردن اتواستارت")
    _disable_autostart()


def _install_global_command() -> None:
    target_dirs = ["/usr/local/bin", str(Path.home() / ".local/bin")]
    wrapper = f'#!/usr/bin/env bash\nexec "{sys.executable}" "{__file__}" "$@"\n'
    for d in target_dirs:
        dst = Path(d) / "aras"
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
            dst.write_text(wrapper, encoding="utf-8")
            os.chmod(dst, 0o755)
            print(green(f"  دستور «aras» ساخته شد: {dst}"))
            if d.endswith(".local/bin"):
                print(dim("  اگر کار نکرد، این را به PATH اضافه کنید: ~/.local/bin"))
            return
        except OSError:
            continue
    print(yellow("  نشد دستور سراسری ساخته شود (دسترسی کافی نبود). "
                 "با ./aras.sh اجرا کنید."))


# ── input helpers ──────────────────────────────────────────────────────
def _ask(prompt: str) -> str:
    try:
        return input(blue("  » ") + prompt + ": ")
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _ask_secret(prompt: str) -> str | None:
    try:
        return getpass.getpass(f"  » {prompt}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _confirm(prompt: str, default: bool = False) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    ans = _ask(f"{prompt} {hint}").strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes", "بله", "آره")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _admin_set() -> bool:
    return bool((_load_json(PANEL_JSON).get("admin") or {}).get("hash"))


def _short(text: str, keep: int = 22) -> str:
    return text if len(text) <= keep else text[:keep] + "…"


def _header(title: str) -> None:
    print()
    print(purple("  ── " + title + " ──"))


# ── menu ───────────────────────────────────────────────────────────────
_W = 52


def _line(ch: str = "─") -> str:
    return "│" + ch * _W + "│"


def _row(text: str) -> str:
    # length ignoring ANSI, to pad the visible box correctly
    visible = re.sub(r"\x1b\[[0-9;]*m", "", text)
    pad = _W - 2 - _display_width(visible)
    return "│  " + text + " " * max(0, pad) + "│"


def _display_width(s: str) -> int:
    # Cell width for the box padding. Persian labels carry zero-width joiners
    # (the نیم‌فاصله, U+200C) and combining marks that take no column — counting
    # them with len() shifts the closing border left on those rows, which is
    # what made the menu look ragged.
    import unicodedata
    width = 0
    for ch in s:
        if ch in ("‌", "‍"):
            continue
        if unicodedata.combining(ch):
            continue
        width += 1
    return width


def draw_menu() -> None:
    running = is_running()
    v = read_version()
    state_txt = green("در حال اجرا") if running else red("متوقف")
    auto_txt = green("بله") if _autostart_installed() else "خیر"

    top = "╔" + "─" * _W + "╗"
    bot = "╚" + "─" * _W + "╝"
    print()
    print(blue(top))
    print(blue(_row(bold("Aras-GP  —  مدیریت پنل"))))
    print(blue(_row(dim(f"نسخه {v}"))))
    print(blue(_line()))
    print(blue(_row("0. خروج")))
    print(blue(_line()))
    print(blue(_row("1. نصب")))
    print(blue(_row("2. به‌روزرسانی")))
    print(blue(_row("3. استفاده از نسخه‌ی مشخص (قدیمی)")))
    print(blue(_row("4. حذف")))
    print(blue(_line()))
    print(blue(_row("5. روشن‌کردن")))
    print(blue(_row("6. خاموش‌کردن")))
    print(blue(_row("7. ری‌استارت")))
    print(blue(_row("8. وضعیت")))
    print(blue(_row("9. لاگ‌ها")))
    print(blue(_line()))
    print(blue(_row("10. تغییر پورت پنل")))
    print(blue(_row("11. تغییر رمز پنل")))
    print(blue(_row("12. مشاهده‌ی تنظیمات")))
    print(blue(_line()))
    print(blue(_row("13. روشن‌کردن اتواستارت")))
    print(blue(_row("14. خاموش‌کردن اتواستارت")))
    print(blue(bot))
    print(f"  وضعیت پنل   : {state_txt}"
          + (dim(f"   http://{panel_host()}:{panel_port()}") if running else ""))
    print(f"  اتواستارت   : {auto_txt}")


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
    "12": action_view_settings,
    "13": action_enable_autostart,
    "14": action_disable_autostart,
}


def menu_loop() -> None:
    while True:
        draw_menu()
        try:
            choice = input(blue("  » ") + "انتخاب کنید [0-14]: ").strip()
        except (EOFError, KeyboardInterrupt):
            # A closed or piped-empty stdin must end the menu, not spin on it.
            print()
            return
        if choice in ("0", "q", "exit", "quit"):
            print(dim("  خدانگهدار."))
            return
        action = ACTIONS.get(choice)
        if not action:
            print(red("  گزینه‌ی نامعتبر."))
            continue
        try:
            action()
        except KeyboardInterrupt:
            print()
        except Exception as exc:      # never let one action crash the menu
            print(red(f"  خطا: {exc}"))
        _ask("Enter برای ادامه")


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
