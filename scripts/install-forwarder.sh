#!/usr/bin/env bash
#
# Aras-GP — fronted forwarder installer (run this ON YOUR VPS).
#
# This is the exit that keeps domain fronting intact:
#
#   browser → relay → TLS(SNI=google.com) → Apps Script → Cloudflare Worker
#           → HTTPS → this forwarder → destination
#
# Your ISP only ever sees a TLS session to Google. The destination sees this
# VPS's IP, which is stable and is not a Cloudflare Workers range — that is
# what makes OpenAI and friends work again.
#
# Cloudflare Workers refuse to forward to plain HTTP, so the forwarder needs a
# real certificate. Two ways, pick one:
#
#   sudo bash install-forwarder.sh --domain fwd.example.com   # Caddy + Let's Encrypt
#   sudo bash install-forwarder.sh --tunnel                   # no domain, Cloudflare Tunnel
#
# Add --uninstall to remove everything.

set -euo pipefail

PORT=8787
DOMAIN=""
USE_TUNNEL=0
AUTH_KEY=""
INSTALL_DIR="/opt/aras-forwarder"
SERVICE="aras-forwarder"

while [ $# -gt 0 ]; do
    case "$1" in
        --domain)   DOMAIN="$2"; shift 2 ;;
        --tunnel)   USE_TUNNEL=1; shift ;;
        --port)     PORT="$2"; shift 2 ;;
        --auth-key) AUTH_KEY="$2"; shift 2 ;;
        --uninstall)
            systemctl disable --now "$SERVICE" aras-tunnel 2>/dev/null || true
            rm -rf "$INSTALL_DIR" \
                   "/etc/systemd/system/$SERVICE.service" \
                   "/etc/systemd/system/aras-tunnel.service"
            systemctl daemon-reload 2>/dev/null || true
            echo "Forwarder removed."
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "Run as root:  sudo bash $0 …" >&2; exit 1; }

if [ -z "$DOMAIN" ] && [ "$USE_TUNNEL" -eq 0 ]; then
    cat >&2 <<'EOF'
Pick how this forwarder gets its HTTPS certificate:

  --domain fwd.example.com   you own a domain and its A record points here
                             (Caddy fetches a Let's Encrypt cert automatically)

  --tunnel                   you have no domain; a Cloudflare Tunnel provides
                             the HTTPS hostname for free

EOF
    exit 1
fi

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
    if   command -v apt-get >/dev/null; then apt-get update -qq && apt-get install -y -qq python3
    elif command -v dnf     >/dev/null; then dnf install -y -q python3
    elif command -v yum     >/dev/null; then yum install -y -q python3
    elif command -v apk     >/dev/null; then apk add --no-cache python3
    else echo "Install python3 first." >&2; exit 1
    fi
    PY="$(command -v python3)"
fi

# The Worker rejects keys shorter than 32 chars, so generate a long one.
if [ -z "$AUTH_KEY" ]; then
    AUTH_KEY="$("$PY" - <<'EOF'
import secrets, string
alphabet = string.ascii_letters + string.digits
print("".join(secrets.choice(alphabet) for _ in range(48)))
EOF
)"
fi

mkdir -p "$INSTALL_DIR"; chmod 750 "$INSTALL_DIR"

# ── the forwarder ─────────────────────────────────────────────────────
cat > "$INSTALL_DIR/forwarder.py" <<'PYEOF'
#!/usr/bin/env python3
"""Upstream forwarder — the far end of the Cloudflare Worker hop.

Wire protocol (matches deploy/cloudflare-worker/worker.js):

    POST /            header x-upstream-auth: <AUTH_KEY>
    body  {"u": url, "m": method, "h": headers, "b": b64, "ct": type, "r": follow}
    reply {"s": status, "h": headers, "b": base64(body)}

Pure standard library so it installs on any distro without a package manager
run. Destinations are never logged: this box sees plaintext URLs, so the only
safe thing to keep is nothing.
"""

import base64
import hmac
import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUTH_KEY = os.environ.get("AUTH_KEY", "")
PORT = int(os.environ.get("PORT", "8787"))
HOST = os.environ.get("HOST", "127.0.0.1")
TIMEOUT = float(os.environ.get("TIMEOUT", "25"))
MAX_BODY = 32 * 1024 * 1024

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("forwarder")

# Hop-by-hop headers the origin must not receive; mirrors the Apps Script side.
SKIP = {"host", "connection", "content-length", "transfer-encoding",
        "proxy-connection", "proxy-authorization", "x-upstream-auth"}

_CTX = ssl.create_default_context()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):        # no request logging, by design
        pass

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._json(200, {"e": "Forwarder is active."})

    def do_POST(self):
        if not hmac.compare_digest(
                self.headers.get("x-upstream-auth", ""), AUTH_KEY):
            self._json(403, {"e": "unauthorized"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"e": "bad length"}); return
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"e": "bad body size"}); return

        try:
            payload = json.loads(self.rfile.read(length))
        except (ValueError, OSError):
            self._json(400, {"e": "bad json"}); return

        url = payload.get("u") or ""
        if not url.lower().startswith(("http://", "https://")):
            self._json(400, {"e": "bad url"}); return

        headers = {k: v for k, v in (payload.get("h") or {}).items()
                   if k.lower() not in SKIP}
        body = None
        if payload.get("b"):
            try:
                body = base64.b64decode(payload["b"])
            except Exception:
                self._json(400, {"e": "bad body"}); return
        if payload.get("ct"):
            headers["Content-Type"] = payload["ct"]

        request = urllib.request.Request(
            url, data=body, headers=headers,
            method=(payload.get("m") or "GET").upper(),
        )

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT,
                                        context=_CTX) as response:
                raw = response.read(MAX_BODY)
                out_headers = {k: v for k, v in response.headers.items()
                               if k.lower() not in ("transfer-encoding",
                                                    "content-encoding",
                                                    "content-length")}
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read(MAX_BODY) if exc.fp else b""
            out_headers = {k: v for k, v in (exc.headers or {}).items()
                           if k.lower() not in ("transfer-encoding",
                                                "content-encoding",
                                                "content-length")}
            status = exc.code
        except Exception as exc:
            self._json(200, {"e": f"upstream fetch failed: {type(exc).__name__}"})
            return

        self._json(200, {"s": status, "h": out_headers,
                         "b": base64.b64encode(raw).decode()})


def main():
    if len(AUTH_KEY) < 32:
        log.error("AUTH_KEY missing or shorter than 32 chars — refusing to run.")
        sys.exit(1)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    log.info("forwarder listening on %s:%d", HOST, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
PYEOF
chmod 750 "$INSTALL_DIR/forwarder.py"

cat > "$INSTALL_DIR/env" <<EOF
AUTH_KEY=$AUTH_KEY
PORT=$PORT
HOST=127.0.0.1
EOF
chmod 600 "$INSTALL_DIR/env"

cat > "/etc/systemd/system/$SERVICE.service" <<EOF
[Unit]
Description=Aras-GP upstream forwarder
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=$INSTALL_DIR/env
ExecStart=$PY $INSTALL_DIR/forwarder.py
Restart=always
RestartSec=3
DynamicUser=yes
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
MemoryMax=256M

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE" >/dev/null 2>&1 || systemctl restart "$SERVICE"

PUBLIC_URL=""

# ── TLS: option A — your own domain, via Caddy ────────────────────────
if [ -n "$DOMAIN" ]; then
    if ! command -v caddy >/dev/null 2>&1; then
        echo "Installing Caddy…"
        if command -v apt-get >/dev/null; then
            apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gnupg >/dev/null
            curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
              | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
            curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
              | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
            apt-get update -qq && apt-get install -y -qq caddy
        elif command -v dnf >/dev/null; then
            dnf install -y -q 'dnf-command(copr)' && dnf copr enable -y @caddy/caddy >/dev/null && dnf install -y -q caddy
        else
            echo "Install Caddy manually, then re-run." >&2; exit 1
        fi
    fi
    cat > /etc/caddy/Caddyfile <<EOF
$DOMAIN {
    reverse_proxy 127.0.0.1:$PORT
}
EOF
    systemctl enable --now caddy >/dev/null 2>&1 || systemctl restart caddy
    for p in 80 443; do
        command -v ufw >/dev/null && ufw allow "$p/tcp" >/dev/null 2>&1 || true
        command -v firewall-cmd >/dev/null && firewall-cmd --permanent --add-port="$p/tcp" >/dev/null 2>&1 || true
    done
    command -v firewall-cmd >/dev/null && firewall-cmd --reload >/dev/null 2>&1 || true
    PUBLIC_URL="https://$DOMAIN"
    echo "Waiting for the certificate…"; sleep 8
fi

# ── TLS: option B — no domain, via Cloudflare Tunnel ──────────────────
if [ "$USE_TUNNEL" -eq 1 ]; then
    if ! command -v cloudflared >/dev/null 2>&1; then
        echo "Installing cloudflared…"
        ARCH="$(uname -m)"
        case "$ARCH" in
            x86_64)  CF_ARCH=amd64 ;;
            aarch64|arm64) CF_ARCH=arm64 ;;
            *) echo "Unsupported arch $ARCH for cloudflared." >&2; exit 1 ;;
        esac
        curl -fsSL -o /usr/local/bin/cloudflared \
          "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-$CF_ARCH"
        chmod +x /usr/local/bin/cloudflared
    fi

    cat > "/etc/systemd/system/aras-tunnel.service" <<EOF
[Unit]
Description=Aras-GP forwarder tunnel
After=$SERVICE.service
Requires=$SERVICE.service

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:$PORT
Restart=always
RestartSec=5
StandardOutput=append:$INSTALL_DIR/tunnel.log
StandardError=append:$INSTALL_DIR/tunnel.log

[Install]
WantedBy=multi-user.target
EOF
    : > "$INSTALL_DIR/tunnel.log"
    systemctl daemon-reload
    systemctl enable --now aras-tunnel >/dev/null 2>&1 || systemctl restart aras-tunnel

    echo "Waiting for the tunnel hostname…"
    for _ in $(seq 1 30); do
        PUBLIC_URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$INSTALL_DIR/tunnel.log" 2>/dev/null | head -1 || true)"
        [ -n "$PUBLIC_URL" ] && break
        sleep 2
    done
    if [ -z "$PUBLIC_URL" ]; then
        echo "Tunnel did not report a hostname. Check: $INSTALL_DIR/tunnel.log" >&2
        exit 1
    fi
fi

sleep 2
systemctl is-active --quiet "$SERVICE" || {
    echo "Forwarder failed to start:" >&2
    journalctl -u "$SERVICE" -n 20 --no-pager >&2 || true
    exit 1
}

cat <<EOF

═══════════════════════════════════════════════════════════════
  Forwarder is running.

  Paste BOTH of these into the panel
  (Settings → AI over Google):

      Forwarder URL:  $PUBLIC_URL
      Auth key:       $AUTH_KEY

═══════════════════════════════════════════════════════════════

  Manage:  systemctl {status|restart|stop} $SERVICE
  Logs:    journalctl -u $SERVICE -f
  Remove:  sudo bash $0 --uninstall
EOF

if [ "$USE_TUNNEL" -eq 1 ]; then
    cat <<'EOF'

  NOTE: a quick tunnel's hostname changes every time cloudflared restarts.
  For a URL that survives reboots, use --domain with a domain you own, or
  set up a named Cloudflare Tunnel.
EOF
fi
