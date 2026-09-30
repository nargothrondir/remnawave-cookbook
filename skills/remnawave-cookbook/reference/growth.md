# Growth — protocols and combinations beyond what runs today

What the pinned stack can already do, what each option costs, and how sure we
are. A row becomes its own page only when it becomes a project (Hysteria2 has
one: `hysteria2.md`). Evidence marks: ✅ verified in source at the pinned
version · 🔶 partly · ❔ not verified.

Versions: Xray v26.6.27 · Remnawave panel 2.8.0 · Mihomo v1.19.31.

## Matrix

| Option | Xray (server) | Panel 2.8 (config + subscription) | Mihomo | Status here | Cost / conflict |
|---|---|---|---|---|---|
| **REALITY TCP (Vision)** | ✅ | ✅ | ✅ | running | none beyond TCP 443 |
| **xHTTP behind Angie (TLS, H2)** | ✅ | ✅ (`securityLayer: TLS`) | ✅ | running | the web server in the data path; secret path |
| **Hysteria2** | ✅ `hysteria` v2, TLS required | ✅ validator + `buildHysteria2Node` | ✅ `type: hysteria2` | running (whole fleet) | UDP port + firewall rule; a certificate (see the panel trap in `hysteria2.md`); UDP is throttled on some networks |
| xHTTP over HTTP/3 (QUIC) | ✅ server needs no H3 when a web server converts H3 → H1/H2 (#4113) | ✅ host ALPN `h3` | ✅ `alpn: [h3]` → HTTP/3 | idea | the web server must listen QUIC on **UDP 443 — the same port Hysteria2 would want**; pick one |
| xHTTP split directions (`downloadSettings`) | ✅ client-side (#4113) | ✅ via the host's `xhttpExtraParams.downloadSettings` | ✅ `download-settings` | idea | a second name or a CDN for one direction; more moving parts |
| xHTTP through a CDN | ✅ packet-up passes most CDNs (#4113) | ✅ (host address = CDN name) | ✅ | idea | a CDN account and a proxied DNS name that is NOT the REALITY name; CDN rules below |
| WebSocket (+ CDN) | 🔶 standard transport | ✅ `ws` allowed; `buildWsOpts` | 🔶 standard | not planned | older fingerprint; xHTTP covers the same CDN case better |
| gRPC (+ CDN) | 🔶 standard transport | ✅ `grpc` allowed; `buildGrpcOpts` | 🔶 standard | not planned | superseded by xHTTP stream-up with its gRPC header disguise (#4113) |
| HTTPUpgrade | 🔶 standard transport | ✅ `httpupgrade` allowed; rendered as ws with HTTP upgrade | 🔶 | not planned | niche; CDN-only use |
| Snippets (shared rules / outbounds) | — | ✅ in 2.8.0; `sync` and root-level merge in 3.x | — | not used | a missing name drops its element silently; no sync in 2.8.0 (`remnawave-2.8.md`, "Snippets") |

## Rules that come with a CDN (from #4113) ✅

- Some CDNs cut a response that carries no data for 100 s; long-lived
  connections need application-level keep-alive (e.g. SSH `ClientAliveInterval`).
  For stream-up, `scStreamUpServerSecs` pads the stream to survive this.
- Cloudflare needs its gRPC support enabled for xHTTP stream-up (the gRPC
  header disguise).
- If a CDN or reverse proxy will not pass xHTTP, use `mode: packet-up` — the
  most compatible.
- The REALITY name must never be proxied by the CDN (it has no REALITY key);
  a CDN needs its own name pointing at the same node.

## Choosing the next step

- **Hysteria2** — the most different traffic shape from the TCP entries
  (UDP/QUIC), so the best hedge against TCP-side blocking; costs a UDP port
  and a certificate decision. Taken in the reference implementation — see
  `hysteria2.md` for the layout that runs and what it measured.
- **xHTTP through a CDN** — hides the node's address from the client path
  entirely; costs a CDN and a second name, and the CDN sees the TLS inside.
- **xHTTP H3** — only if UDP 443 is not given to Hysteria2.

Each is a profile change (a new inbound next to the existing ones), so the
rules in `automation.md` apply: add, never rewrite; one node first.
