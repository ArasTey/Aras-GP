// Cloudflare Worker — the relay hop, and only that.
//
// POST → the owner's domain-fronting relay (GAS → here → destination). This is
// what the desktop engine talks to, and it carries the operator's own traffic.
//
// It used to also be a VLESS server for other people's phones. That moved to
// deploy/share-worker/worker.js, deployed separately under its own name.
// Running a proxy for other people is what Cloudflare's terms disallow, so it
// does not belong in the deployment the operator's own connectivity depends
// on: if the share Worker is taken down, this one keeps working.

const WORKER_URL = "myworker.workers.dev";

// Shared secret the desktop engine's relay engine puts in every payload
// ("k"). Substituted at deploy time by the panel (panel/cloudflare.py). When
// empty the check is skipped — the historical unauthenticated behaviour.
// Without this the Worker accepts any POST with a URL, so a discovered
// workers.dev URL made it an open fetch proxy carrying other people's traffic
// on this account's request quotas.
const AUTH_KEY = "__ARAS_AUTH_KEY__";

export default {
    async fetch(request, env) {
        try {
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

            if (!req.u || typeof req.u !== "string") {
                return json({ e: "missing url" }, 400);
            }

            if (AUTH_KEY && req.k !== AUTH_KEY) {
                return json({ e: "unauthorized" }, 403);
            }

            const targetUrl = new URL(req.u);

            // Self-fetch guard: the relay must not relay to itself. Exact
            // hostname or subdomain only — endsWith(workers.dev) alone would
            // match a lookalike like "evil-workers.dev" and refuse legit
            // traffic aimed there instead.
            const selfHost = WORKER_URL.toLowerCase();
            const targetHost = targetUrl.hostname.toLowerCase().replace(/\.$/, "");
            if (targetHost === selfHost || targetHost.endsWith("." + selfHost)) {
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
