---
name: remnawave-cookbook
description: >-
  Use when designing, operating or debugging a Remnawave VPN fleet built as
  VLESS + Reality (TCP, Vision) with a self-steal decoy site behind Angie/nginx
  on a unix socket, plus VLESS over xHTTP on the same port 443 through that web
  server, for Mihomo (Clash.Meta) clients — and when automating it through the
  Remnawave panel API. Triggers on: Remnawave profile / inbound / host / squad /
  node, inbound tags, xHTTP behind nginx or Angie, grpc_pass vs proxy_pass,
  trustedXForwardedFor, Reality dest on a unix socket, Mihomo xhttp-opts /
  reuse-settings, "node switched off", "xHTTP does not connect", "delay test
  fails", Hysteria2 / CDN / WebSocket as next steps. Facts are pinned to
  verified versions and cite the upstream file they come from.
---

# remnawave-cookbook

A field-tested recipe for one architecture, and the facts it rests on — each
checked against the upstream source at the version it names. Written from a
real fleet, with everything that would identify it removed.

## The architecture in one picture

```
                               :443/tcp (the only public port that carries users)
 Mihomo ──TLS──▶ Xray, VLESS + REALITY (Vision)
                   │
   REALITY client ─┤──▶ decrypt, proxy the user's traffic
                   │
   anything else ──┘──▶ raw bytes + PROXY protocol (xver 1)
                        ──▶ Angie on unix:/dev/shm/nginx.sock (ssl proxy_protocol)
                             ├─ location <secret xHTTP path> ──grpc_pass──▶ unix:/dev/shm/xhttp.sock
                             │                                              Xray, VLESS + xHTTP (no TLS)
                             └─ everything else ──▶ decoy website (own ACME certificate)
```

Two ways in, one port. A browser, a scanner or a censor's probe sees an
ordinary HTTPS site with a valid certificate. A REALITY client is handled by
Xray itself. An xHTTP client does plain TLS to the site's own name and is
handed, on one secret path, to the xHTTP inbound. Details and ports:
`reference/architecture.md`.

## Invariants (break one and it silently stops working)

Every line is **verified** against the source named in the reference files
unless marked otherwise.

1. **An inbound's tag is its identity in the panel, and it is unique across the
   whole panel**, not per profile. Renaming a tag re-creates the inbound: its
   squad membership and node activation are deleted by cascade and its host is
   left pointing at nothing. Never rename by hand; migrate with a snapshot of
   the bindings (`reference/remnawave-2.8.md`).
2. **A node left with no active inbound is switched off by the panel** when the
   profile's nodes restart, and detached from its profile. Re-binding does not
   switch it back on — that is a separate call.
3. **Profile changes restart Xray** on every node of that profile. Users
   reconnect once. Guard every write so it happens only when something is
   actually missing.
4. **The xHTTP inbound listens on a unix socket with no TLS of its own.** Xray
   ignores `port` for a socket listener, but give it `443` anyway: the panel's
   host form fills its required port from the inbound.
5. **Client addresses reach Xray only through `trustedXForwardedFor`**, which
   lists header NAMES whose presence makes `X-Forwarded-For` trusted. The web
   server sets and overwrites both (`X-Real-IP` as the marker). Without it Xray
   logs a warning per request and records the socket as the client.
6. **The web server hop is `grpc_pass` by default** — it streams the request
   body; `proxy_pass` only fits with `proxy_request_buffering off`. Timeouts on
   that hop sit ABOVE Xray's own idle timeout (300 s) so Xray, which sees both
   directions, decides. `access_log off` on the xHTTP location
   (`reference/angie.md`).
7. **Mihomo needs `reuse-settings` (xmux) in the subscription**, delivered via
   the host's `xhttpExtraParams`. Without it Mihomo opens a new TCP+TLS
   connection for every proxied connection.
8. **The VLESS flow `xtls-rprx-vision` belongs to TCP/raw with REALITY or TLS
   only**; the panel computes it per inbound, so an xHTTP inbound gets none.
9. **Publish nothing that identifies the fleet**: no IP addresses, domains,
   provider or node names — not in code, commits, issues or logs pasted
   anywhere public.
10. ❔ **Before moving past Xray v26.6.27, check REALITY `minClientVer`.** A newer
    default that refuses older clients is reported upstream; sources disagree
    on the version. Verify in the pinned source before upgrading.

## Verified versions

| Component | Version | Notes |
|---|---|---|
| Remnawave panel (backend) | 2.8.0 | API contracts in `reference/remnawave-2.8.md` |
| Remnawave node | 2.8.0 | bundles Xray v26.6.27 |
| Xray-core | v26.6.27 | `reference/xray-v26.6.27.md` |
| Mihomo | v1.19.31 | `reference/mihomo.md` |
| Angie | 1.12.x (`-templated` image) | `reference/angie.md` |

Facts are tied to these versions. A newer one may behave differently — check
the same file at the new tag before relying on it (`reference/sources.md`).

## Where to look

| Task | File |
|---|---|
| How traffic flows, ports, what listens where | `reference/architecture.md` |
| Panel model, API contracts, tag identity, auto-disable | `reference/remnawave-2.8.md` |
| Xray: REALITY on a socket, xHTTP settings and defaults, timeouts, trusted headers | `reference/xray-v26.6.27.md` |
| Where each fact comes from and how to re-check it | `reference/sources.md` |

More reference pages, diagnostics, the operations map, the offline validator
and the fleet audit arrive in the next stages of this repository.

## How to answer

- **Reference** — open the matching `reference/` file and answer from it, with
  its evidence mark. Do not fill gaps from memory: say what is unverified.
- **A fact is missing or the version differs** — say so, and point at the
  upstream file to read (`reference/sources.md`), rather than guessing.
