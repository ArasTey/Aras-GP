#!/usr/bin/env bash
#
# Aras-GP — exit node installer.
#
# Run this ON YOUR VPS. It installs a small authenticated SOCKS5 server, wires
# it into systemd so it survives reboots, opens the port, and prints one line to
# paste into the panel.
#
#   curl -fsSL <raw-url>/scripts/install-exit-node.sh | sudo bash
# or
#   sudo bash install-exit-node.sh --port 1080 --user aras
#
# Why a SOCKS5 exit: traffic leaving through Cloudflare Workers arrives from
# Cloudflare's ranges, which OpenAI and similar services refuse outright. A
# proxy on a box you control gives those hosts a stable IP that is not on a
# blocklist. The panel sends only the hosts you choose through here.
#
# No dependencies beyond Python 3, which every modern distro already ships.

set -euo pipefail

PORT=1080
USERNAME="aras"
PASSWORD=""
BIND="0.0.0.0"
INSTALL_DIR="/opt/aras-exit"
SERVICE="aras-exit"

while [ $# -gt 0 ]; do
    case "$1" in
        --port)     PORT="$2"; shift 2 ;;
        --user)     USERNAME="$2"; shift 2 ;;
        --password) PASSWORD="$2"; shift 2 ;;
        --bind)     BIND="$2"; shift 2 ;;
        --uninstall)
            systemctl disable --now "$SERVICE" 2>/dev/null || true
            rm -rf "$INSTALL_DIR" "/etc/systemd/system/$SERVICE.service"
            systemctl daemon-reload 2>/dev/null || true
            echo "Exit node removed."
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root:  sudo bash $0" >&2
    exit 1
fi

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
    echo "Installing python3…"
    if   command -v apt-get >/dev/null; then apt-get update -qq && apt-get install -y -qq python3
    elif command -v dnf     >/dev/null; then dnf install -y -q python3
    elif command -v yum     >/dev/null; then yum install -y -q python3
    elif command -v apk     >/dev/null; then apk add --no-cache python3
    else echo "Install python3 manually, then re-run." >&2; exit 1
    fi
    PY="$(command -v python3)"
fi

# A password the operator did not choose is a password nobody will reuse.
if [ -z "$PASSWORD" ]; then
    PASSWORD="$("$PY" - <<'EOF'
import secrets, string
alphabet = string.ascii_letters + string.digits
print("".join(secrets.choice(alphabet) for _ in range(24)))
EOF
)"
fi

mkdir -p "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"

# ── the server ────────────────────────────────────────────────────────
cat > "$INSTALL_DIR/exit_node.py" <<'PYEOF'
#!/usr/bin/env python3
"""Minimal authenticated SOCKS5 server (RFC 1928 / RFC 1929).

Deliberately small: one asyncio server, no dependencies, no disk writes, no
logging of destinations. It exists to give the operator's relay a stable exit
IP, so it should keep no record of where that traffic went.
"""

import asyncio
import ipaddress
import logging
import os
import socket
import struct
import sys

USERNAME = os.environ.get("ARAS_USER", "")
PASSWORD = os.environ.get("ARAS_PASS", "")
BIND = os.environ.get("ARAS_BIND", "0.0.0.0")
PORT = int(os.environ.get("ARAS_PORT", "1080"))
IDLE_TIMEOUT = 300
# Reaching RFC1918 / loopback through the exit is refused by default: an open
# relay on a public IP is otherwise a free port-scanner for the provider's
# internal network, which is how VPS accounts get terminated. Set
# ARAS_ALLOW_PRIVATE=1 only when the exit is deliberately serving a LAN.
ALLOW_PRIVATE = os.environ.get("ARAS_ALLOW_PRIVATE", "") in ("1", "true", "yes")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("exit")

# Destinations the exit must never open on someone else's behalf. Without this
# an open relay on a public IP becomes a tool for scanning the provider's
# internal network, which gets the VPS terminated.
_BLOCKED = [
    ipaddress.ip_network(n) for n in (
        "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
        "169.254.0.0/16", "::1/128", "fc00::/7", "fe80::/10",
    )
]


def _is_private(host: str) -> bool:
    if ALLOW_PRIVATE:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in net for net in _BLOCKED)


async def _pipe(src, dst):
    try:
        while True:
            data = await asyncio.wait_for(src.read(65536), timeout=IDLE_TIMEOUT)
            if not data:
                break
            dst.write(data)
            await dst.drain()
    except (asyncio.TimeoutError, ConnectionError, asyncio.CancelledError):
        pass
    except Exception:
        pass
    finally:
        try:
            if not dst.is_closing():
                dst.close()
        except Exception:
            pass


async def handle(reader, writer):
    peer = writer.get_extra_info("peername")
    remote_w = None
    try:
        head = await asyncio.wait_for(reader.readexactly(2), timeout=15)
        if head[0] != 5:
            return
        methods = await asyncio.wait_for(reader.readexactly(head[1]), timeout=10)

        if USERNAME:
            if 0x02 not in methods:
                writer.write(b"\x05\xff"); await writer.drain(); return
            writer.write(b"\x05\x02"); await writer.drain()
            ver = await asyncio.wait_for(reader.readexactly(2), timeout=10)
            if ver[0] != 1:
                return
            user = (await reader.readexactly(ver[1])).decode("utf-8", "replace")
            plen = (await reader.readexactly(1))[0]
            pw = (await reader.readexactly(plen)).decode("utf-8", "replace")
            import hmac
            ok = (hmac.compare_digest(user, USERNAME)
                  and hmac.compare_digest(pw, PASSWORD))
            writer.write(b"\x01\x00" if ok else b"\x01\x01")
            await writer.drain()
            if not ok:
                log.info("auth rejected from %s", peer[0] if peer else "?")
                return
        else:
            if 0x00 not in methods:
                writer.write(b"\x05\xff"); await writer.drain(); return
            writer.write(b"\x05\x00"); await writer.drain()

        req = await asyncio.wait_for(reader.readexactly(4), timeout=15)
        if req[1] != 1:
            writer.write(b"\x05\x07\x00\x01" + b"\x00" * 6)
            await writer.drain(); return

        atyp = req[3]
        if atyp == 1:
            host = socket.inet_ntoa(await reader.readexactly(4))
        elif atyp == 3:
            length = (await reader.readexactly(1))[0]
            host = (await reader.readexactly(length)).decode("utf-8", "replace")
        elif atyp == 4:
            host = socket.inet_ntop(socket.AF_INET6, await reader.readexactly(16))
        else:
            writer.write(b"\x05\x08\x00\x01" + b"\x00" * 6)
            await writer.drain(); return
        port = struct.unpack("!H", await reader.readexactly(2))[0]

        if _is_private(host):
            writer.write(b"\x05\x02\x00\x01" + b"\x00" * 6)
            await writer.drain(); return

        try:
            remote_r, remote_w = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=15)
        except Exception:
            writer.write(b"\x05\x04\x00\x01" + b"\x00" * 6)
            await writer.drain(); return

        writer.write(b"\x05\x00\x00\x01" + b"\x00" * 6)
        await writer.drain()
        await asyncio.gather(_pipe(reader, remote_w), _pipe(remote_r, writer))

    except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError):
        pass
    except Exception as exc:
        log.debug("session error: %s", exc)
    finally:
        for w in (writer, remote_w):
            try:
                if w and not w.is_closing():
                    w.close()
            except Exception:
                pass


async def main():
    if not USERNAME or not PASSWORD:
        log.error("ARAS_USER and ARAS_PASS must be set — refusing to run open.")
        sys.exit(1)
    server = await asyncio.start_server(handle, BIND, PORT)
    log.info("exit node listening on %s:%d", BIND, PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
PYEOF

chmod 750 "$INSTALL_DIR/exit_node.py"

# ── credentials, readable only by root ────────────────────────────────
cat > "$INSTALL_DIR/env" <<EOF
ARAS_USER=$USERNAME
ARAS_PASS=$PASSWORD
ARAS_BIND=$BIND
ARAS_PORT=$PORT
EOF
chmod 600 "$INSTALL_DIR/env"

# ── systemd unit ──────────────────────────────────────────────────────
cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Aras-GP exit node (SOCKS5)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$INSTALL_DIR/env
ExecStart=$PY $INSTALL_DIR/exit_node.py
Restart=always
RestartSec=3
DynamicUser=yes
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
RestrictAddressFamilies=AF_INET AF_INET6
MemoryMax=192M

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE" >/dev/null 2>&1 || systemctl restart "$SERVICE"

# ── firewall ──────────────────────────────────────────────────────────
if command -v ufw >/dev/null 2>&1; then
    ufw allow "$PORT/tcp" >/dev/null 2>&1 || true
elif command -v firewall-cmd >/dev/null 2>&1; then
    firewall-cmd --permanent --add-port="$PORT/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
fi

sleep 2
if ! systemctl is-active --quiet "$SERVICE"; then
    echo "Service failed to start. Logs:" >&2
    journalctl -u "$SERVICE" -n 20 --no-pager >&2 || true
    exit 1
fi

IP="$(curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"

cat <<EOF

═══════════════════════════════════════════════════════════════
  Exit node is running.

  Paste this single line into the panel
  (Settings → AI / static-IP exit):

      socks5://$USERNAME:$PASSWORD@$IP:$PORT

═══════════════════════════════════════════════════════════════

  Manage:   systemctl {status|restart|stop} $SERVICE
  Logs:     journalctl -u $SERVICE -f
  Remove:   sudo bash $0 --uninstall

  Keep that line secret — it is a working proxy credential.
EOF
