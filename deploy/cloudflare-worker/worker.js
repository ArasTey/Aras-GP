// Cloudflare Worker — two jobs in one script.
//
// 1. POST  → the owner's domain-fronting relay hop (GAS → here → destination).
//            Unchanged; this is what the desktop engine talks to.
//
// 2. WebSocket upgrade → a VLESS server for friends' phones.
//            The panel has no VPS, so the Worker itself is the VLESS server:
//            it reads the VLESS header off the WebSocket, checks the UUID
//            against a list bound at deploy time, opens a TCP socket to the
//            requested target from Cloudflare's edge, and pipes the two
//            together. workers.dev is reachable worldwide and behind CGNAT,
//            so a friend needs nothing but a VLESS app and the link.
//
// The two paths never collide: the relay is POST/GET, the VLESS server is a
// WebSocket upgrade, and each returns before the other's code runs.

import { connect } from "cloudflare:sockets";

const WORKER_URL = "myworker.workers.dev";

export default {
    async fetch(request, env) {
        try {
            // ── VLESS over WebSocket ──────────────────────────────────
            if (request.headers.get("Upgrade") === "websocket") {
                return await handleVless(request, env);
            }

            if (request.headers.get("x-relay-hop") === "1") {
                return json({ e: "loop detected" }, 508);
            }

            if (request.method === "GET") {
                // A plain browser hit should look like nothing interesting.
                return new Response("", { status: 200 });
            }

            if (request.method !== "POST") {
                return json({ e: "Method not allowed." }, 405);
            }

            const req = await request.json();

            if (!req.u) {
                return json({ e: "missing url" }, 400);
            }

            const targetUrl = new URL(req.u);

            const BLOCKED_HOSTS = [
                WORKER_URL,
            ];

            if (BLOCKED_HOSTS.some(h => targetUrl.hostname.endsWith(h))) {
                return json({ e: "self-fetch blocked" }, 400);
            }

            const headers = new Headers();
            if (req.h && typeof req.h === "object") {
                for (const [k, v] of Object.entries(req.h)) {
                    headers.set(k, v);
                }
            }

            headers.set("x-relay-hop", "1");

            const fetchOptions = {
                method: (req.m || "GET").toUpperCase(),
                headers,
                redirect: req.r === false ? "manual" : "follow"
            };

            if (req.b) {
                fetchOptions.body = Uint8Array.from(atob(req.b), c => c.charCodeAt(0));
            }

            const resp = await fetch(targetUrl.toString(), fetchOptions);

            // Read response safely (no stack overflow)
            const buffer = await resp.arrayBuffer();
            const uint8 = new Uint8Array(buffer);

            let binary = "";
            const chunkSize = 0x8000; // prevent call stack overflow

            for (let i = 0; i < uint8.length; i += chunkSize) {
                binary += String.fromCharCode.apply(
                    null,
                    uint8.subarray(i, i + chunkSize)
                );
            }

            const base64 = btoa(binary);

            const responseHeaders = {};
            resp.headers.forEach((v, k) => {
                responseHeaders[k] = v;
            });

            return json({
                s: resp.status,
                h: responseHeaders,
                b: base64
            });

        } catch (err) {
            return json({ e: String(err) }, 500);
        }
    }
};

function json(obj, status = 200) {
    return new Response(JSON.stringify(obj), {
        status,
        headers: {
            "content-type": "application/json"
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
        return new Response("not configured", { status: 503 });
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

function parseVlessHeader(bytes, uuids) {
    if (bytes.length < 24) return { error: "short" };

    const version = bytes[0];
    const uuid = bytesToHex(bytes.subarray(1, 17));
    if (!uuids.includes(uuid)) return { error: "auth" };

    const addonLen = bytes[17];
    let i = 18 + addonLen;

    const command = bytes[i++];
    // 1 = TCP. UDP (2) is used mainly for DNS; browsing works over TCP, and
    // refusing UDP cleanly beats half-supporting it.
    if (command !== 1) return { error: "command" };

    const port = (bytes[i] << 8) | bytes[i + 1];
    i += 2;

    const type = bytes[i++];
    let address = "";
    if (type === 1) {                       // IPv4
        address = `${bytes[i]}.${bytes[i + 1]}.${bytes[i + 2]}.${bytes[i + 3]}`;
        i += 4;
    } else if (type === 2) {                // domain name
        const len = bytes[i++];
        address = new TextDecoder().decode(bytes.subarray(i, i + len));
        i += len;
    } else if (type === 3) {                // IPv6
        const parts = [];
        for (let j = 0; j < 8; j++) {
            parts.push(((bytes[i + j * 2] << 8) | bytes[i + j * 2 + 1]).toString(16));
        }
        address = parts.join(":");
        i += 16;
    } else {
        return { error: "addr-type" };
    }

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
