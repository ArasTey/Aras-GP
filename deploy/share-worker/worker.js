// Aras-GP — share worker.
//
// Deliberately not the relay. The relay Worker is a JSON fetch proxy the panel
// drives; this one is a VLESS server plus the subscription its clients fetch,
// and the two never share a deployment. Keeping them apart means the terms-of-
// service risk that comes with running a proxy for other people cannot reach
// the relay: if Cloudflare takes this script down, the relay keeps working.
//
// It answers exactly two things:
//
//   WebSocket upgrade   → a VLESS session, if the UUID is bound and the path
//                         matches the deployment's secret path.
//   GET <SUB_PATH>      → the subscription, base64 as the phone apps expect.
//
// Everything else is an empty 200. There is no UI, no status page and no
// index: a page that says what this is would be the easiest way to find it.
//
// Bindings written at deploy time:
//   VLESS_UUIDS  JSON array of allowed UUIDs
//   WS_PATH      the WebSocket path this deployment answers on
//   SUB_PATH     the subscription path, unrelated to WS_PATH
//   SUB_BODY     the subscription, already base64-encoded
//
// The paths are per-deployment random strings rather than anything guessable,
// so scanning workers.dev for a known path finds nothing.

// The VLESS session opens a raw TCP socket to the destination from
// Cloudflare's edge, which is the one capability that makes this work without
// a VPS.
import { connect } from "cloudflare:sockets";

export default {
    async fetch(request, env) {
        try {
            const url = new URL(request.url);

            if (request.headers.get("Upgrade") === "websocket") {
                // Wrong path is treated exactly like any other unknown
                // request, so probing cannot tell a real deployment from a
                // wrong guess.
                if (!pathMatches(url.pathname, env.WS_PATH)) {
                    return blank();
                }
                return await handleVless(request, env);
            }

            if (request.method === "GET"
                && env.SUB_PATH
                && pathMatches(url.pathname, env.SUB_PATH)) {
                return subscription(env);
            }

            return blank();
        } catch (err) {
            // Never leak a stack trace; an error page is a fingerprint too.
            return blank();
        }
    }
};

// An empty 200 for everything unrecognised. A 404 would distinguish "wrong
// path on a real deployment" from "nothing here", which is the distinction
// worth denying.
function blank() {
    return new Response("", {
        status: 200,
        headers: { "content-type": "text/plain; charset=utf-8" }
    });
}

function pathMatches(actual, expected) {
    if (!expected) return false;
    const a = String(actual || "").replace(/\/+$/, "") || "/";
    const b = String(expected).replace(/\/+$/, "") || "/";
    return a === b;
}

function subscription(env) {
    const body = String(env.SUB_BODY || "");
    if (!body) return blank();
    return new Response(body, {
        status: 200,
        headers: {
            "content-type": "text/plain; charset=utf-8",
            // Apps re-fetch this; letting a CDN hold it means a revoked client
            // keeps working from cache.
            "cache-control": "no-store"
        }
    });
}

// ─────────────────────────────────────────────────────────────────────────
// VLESS over WebSocket
// ─────────────────────────────────────────────────────────────────────────

// UUIDs are bound at deploy time as env.VLESS_UUIDS — a JSON array of strings,
// or a single UUID. The panel writes this binding when it deploys the Worker;
// with none set the VLESS server refuses every client rather than becoming an
// open proxy anyone who finds the URL can ride.
function allowedUuids(env) {
    const raw = (env && env.VLESS_UUIDS) || "";
    if (!raw) return [];
    try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.map(normalizeUuid) : [normalizeUuid(parsed)];
    } catch {
        return raw.split(",").map(s => normalizeUuid(s.trim())).filter(Boolean);
    }
}

function normalizeUuid(u) {
    return String(u || "").toLowerCase().replace(/[^0-9a-f]/g, "");
}

async function handleVless(request, env) {
    const uuids = allowedUuids(env);
    if (uuids.length === 0) {
        // Same blank 200 as any unrecognised request. A distinct "not
        // configured" told a prober that a real deployment lived here and was
        // merely unarmed, which is exactly the fact worth withholding.
        return blank();
    }

    const pair = new WebSocketPair();
    const client = pair[0];
    const server = pair[1];
    server.accept();

    // v2rayNG and friends can carry the first VLESS bytes in the
    // Sec-WebSocket-Protocol header (0-RTT "early data") instead of a first
    // frame; accept both so the config works whichever the app chooses.
    const earlyDataHeader = request.headers.get("sec-websocket-protocol") || "";

    handleVlessSession(server, earlyDataHeader, uuids).catch(() => {
        safeClose(server);
    });

    return new Response(null, { status: 101, webSocket: client });
}

async function handleVlessSession(ws, earlyDataHeader, uuids) {
    let remote = null;
    let headerParsed = false;

    const early = base64ToBytes(earlyDataHeader);
    if (early && early.length) {
        remote = await onClientChunk(early, ws, remote, uuids, () => { headerParsed = true; });
    }

    ws.addEventListener("message", async (event) => {
        try {
            const chunk = new Uint8Array(
                event.data instanceof ArrayBuffer ? event.data : await event.data.arrayBuffer()
            );
            if (!headerParsed) {
                remote = await onClientChunk(chunk, ws, remote, uuids, () => { headerParsed = true; });
            } else if (remote) {
                const writer = remote.writable.getWriter();
                await writer.write(chunk);
                writer.releaseLock();
            }
        } catch {
            safeClose(ws);
        }
    });

    ws.addEventListener("close", () => { if (remote) safeCloseSocket(remote); });
    ws.addEventListener("error", () => { if (remote) safeCloseSocket(remote); });
}

// Parse the VLESS header from the first chunk, open the TCP socket, send the
// VLESS reply, forward any leftover payload, and start pumping the socket back
// to the WebSocket.
async function onClientChunk(chunk, ws, remote, uuids, markParsed) {
    if (remote) return remote;   // header already handled by an earlier call

    const parsed = parseVlessHeader(chunk, uuids);
    if (parsed.error) {
        safeClose(ws);
        return null;
    }
    // The destination is whatever the client asked for, which is the point of
    // a proxy — but "anywhere" should not include the inside of Cloudflare's
    // network or anyone's LAN. An authenticated client could otherwise use
    // this Worker to reach addresses that are not on the public internet.
    if (isPrivateDestination(parsed.address)) {
        safeClose(ws);
        return null;
    }

    markParsed();

    // VLESS reply: [version, addon-length=0]. Sent once, ahead of real data.
    ws.send(new Uint8Array([parsed.version, 0]));

    const socket = connect({ hostname: parsed.address, port: parsed.port });
    remote = socket;

    // Payload that rode in after the header goes out first.
    if (parsed.payload && parsed.payload.length) {
        const writer = socket.writable.getWriter();
        await writer.write(parsed.payload);
        writer.releaseLock();
    }

    pumpSocketToWs(socket, ws);
    return socket;
}

// Destinations that are not on the public internet. Checked on the literal
// address the client sent: a hostname that resolves into one of these still
// gets through, so this is a guard against the obvious attempt rather than a
// complete boundary — the complete one would need resolution the Worker
// runtime does not offer before connect().
function isPrivateDestination(address) {
    const host = String(address || "").toLowerCase().replace(/^\[|\]$/g, "");
    if (!host) return true;

    if (host === "localhost" || host.endsWith(".localhost")
        || host.endsWith(".local") || host.endsWith(".internal")) {
        return true;
    }

    // IPv6 loopback, unspecified, unique-local (fc00::/7), link-local (fe80::/10).
    if (host.includes(":")) {
        if (host === "::1" || host === "::") return true;
        const head = host.split(":")[0];
        if (/^f[cd]/.test(head)) return true;
        if (/^fe[89ab]/.test(head)) return true;
        return false;
    }

    const parts = host.split(".");
    if (parts.length !== 4 || !parts.every(p => /^\d{1,3}$/.test(p))) {
        return false;                       // a domain name; nothing to judge
    }
    const [a, b] = parts.map(Number);
    if (parts.some(p => Number(p) > 255)) return true;
    if (a === 0 || a === 10 || a === 127) return true;          // this net, private, loopback
    if (a === 169 && b === 254) return true;                    // link-local
    if (a === 172 && b >= 16 && b <= 31) return true;           // private
    if (a === 192 && b === 168) return true;                    // private
    if (a === 100 && b >= 64 && b <= 127) return true;          // CGNAT
    if (a === 198 && (b === 18 || b === 19)) return true;        // benchmark
    if (a >= 224) return true;                                  // multicast, reserved
    return false;
}

// These bytes come off the wire from whoever connected, so every field is
// read only after checking the buffer actually reaches that far. Without the
// checks a truncated header walked past the end: reads return undefined,
// `undefined << 8` is 0, and the parse yielded port 0 or a domain cut short —
// a dial to somewhere nobody asked for, from a header the sender controls.
function parseVlessHeader(bytes, uuids) {
    // version(1) + uuid(16) + addonLen(1) + command(1) + port(2) + type(1)
    if (bytes.length < 23) return { error: "short" };

    const version = bytes[0];
    const uuid = bytesToHex(bytes.subarray(1, 17));
    if (!uuids.includes(uuid)) return { error: "auth" };

    const addonLen = bytes[17];
    let i = 18 + addonLen;
    // command(1) + port(2) + type(1) must still fit.
    if (i + 4 > bytes.length) return { error: "short" };

    const command = bytes[i++];
    // 1 = TCP. UDP (2) is used mainly for DNS; browsing works over TCP, and
    // refusing UDP cleanly beats half-supporting it.
    if (command !== 1) return { error: "command" };

    const port = (bytes[i] << 8) | bytes[i + 1];
    i += 2;
    if (port === 0) return { error: "port" };

    const type = bytes[i++];
    let address = "";
    if (type === 1) {                       // IPv4
        if (i + 4 > bytes.length) return { error: "short" };
        address = `${bytes[i]}.${bytes[i + 1]}.${bytes[i + 2]}.${bytes[i + 3]}`;
        i += 4;
    } else if (type === 2) {                // domain name
        if (i + 1 > bytes.length) return { error: "short" };
        const len = bytes[i++];
        // subarray would clamp silently and hand back a truncated name, which
        // resolves to something other than what was asked for.
        if (len === 0 || i + len > bytes.length) return { error: "short" };
        address = new TextDecoder().decode(bytes.subarray(i, i + len));
        i += len;
    } else if (type === 3) {                // IPv6
        if (i + 16 > bytes.length) return { error: "short" };
        const parts = [];
        for (let j = 0; j < 8; j++) {
            parts.push(((bytes[i + j * 2] << 8) | bytes[i + j * 2 + 1]).toString(16));
        }
        address = parts.join(":");
        i += 16;
    } else {
        return { error: "addr-type" };
    }

    if (!address) return { error: "addr" };
    return { version, port, address, payload: bytes.subarray(i) };
}

async function pumpSocketToWs(socket, ws) {
    try {
        const reader = socket.readable.getReader();
        for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            if (ws.readyState === 1 && value) ws.send(value);
        }
    } catch {
        // fall through to close
    }
    safeClose(ws);
    safeCloseSocket(socket);
}

// ── small helpers ─────────────────────────────────────────────────────────

function bytesToHex(bytes) {
    let hex = "";
    for (let i = 0; i < bytes.length; i++) {
        hex += bytes[i].toString(16).padStart(2, "0");
    }
    return hex;
}

function base64ToBytes(b64) {
    if (!b64) return null;
    try {
        // WebSocket subprotocol uses URL-safe base64 without padding.
        const s = b64.replace(/-/g, "+").replace(/_/g, "/");
        const bin = atob(s);
        const out = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
        return out;
    } catch {
        return null;
    }
}

function safeClose(ws) {
    try { ws.close(); } catch { /* already closing */ }
}

function safeCloseSocket(socket) {
    try { socket.close(); } catch { /* already closing */ }
}
