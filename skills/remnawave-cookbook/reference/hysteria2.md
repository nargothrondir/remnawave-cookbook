# Hysteria2 — the third protocol, next to REALITY TCP and xHTTP

Status in the reference implementation: **running on one node** (since
2026-09-26), measured with a Mihomo client; the rest of the fleet follows one
node at a time. Evidence marks: ✅ verified at the tag · 🔶 partly / observed in
operation · ❔ not verified · 💡 design consideration.

## Support across the stack

| Layer | Version | Support | Evidence |
|---|---|---|---|
| Xray server | v26.6.27 | inbound `protocol: "hysteria"`, `settings.version: 2` only; transport `network: "hysteria"` + `hysteriaSettings` | ✅ `infra/conf/hysteria.go`, `infra/conf/transport_internet.go` |
| Remnawave panel | 2.8.0 | `hysteria` allowed as protocol and network; users added with `auth` = the user's VLESS UUID | ✅ `xray-config.validator.ts` (`ALLOWED_PROTOCOLS`, `addUsersToInbound`) |
| Remnawave node | 2.8.0 | adds and removes hysteria users at run time | ✅ `src/modules/handler/handler.service.ts` (`addHysteriaUser`) |
| Subscription for Mihomo | 2.8.0 | `type: hysteria2`, rendered by `buildHysteria2Node` | ✅ `mihomo.generator.service.ts` |
| Mihomo client | v1.19.31 | `type: hysteria2` | ✅ `adapter/outbound/hysteria2.go`; 🔶 carries traffic in operation |

## The layout that runs

```
client ── UDP 443 ──▶ Xray hysteria inbound (TLS: the node's own certificate)
       ── TCP 443 ──▶ Xray REALITY inbound ──▶ web server (decoy, xHTTP)
```

- **UDP 443**, the same number as REALITY on TCP: to an observer the node is
  one HTTPS site that also speaks HTTP/3. Nothing else on the node uses UDP,
  so the host firewall opens exactly this port when the protocol is switched
  on, not before.
- **No obfuscation, no port hopping.** `salamander` would make the traffic stop
  looking like HTTP/3 with a real certificate, which is the point of UDP 443.
  Port hopping stays in reserve for a network that blocks the single port.

The inbound:

```json
{
  "tag": "XX-HYSTERIA2-QUIC-TLS",
  "port": 443,
  "protocol": "hysteria",
  "settings": { "version": 2, "clients": [] },
  "streamSettings": {
    "network": "hysteria",
    "security": "tls",
    "tlsSettings": {
      "alpn": ["h3"],
      "certificates": [{
        "certificateFile": "/etc/xray-tls/letsencrypt/certificate.pem",
        "keyFile": "/etc/xray-tls/letsencrypt/private.key"
      }]
    },
    "hysteriaSettings": {
      "version": 2,
      "masquerade": { "type": "proxy", "url": "https://node.example.com", "rewriteHost": true }
    }
  }
}
```

The subscription host: the node's name as address and SNI, port 443, ALPN
`h3`. Nothing else — see the pin trap below.

## Server side (Xray v26.6.27)

- **TLS is mandatory.** The listener refuses to start without it
  (`tls config is nil`, `transport/internet/hysteria/hub.go`) and offers ALPN
  `h3`. ✅
- **Users.** `settings.clients[].auth`; the panel fills it with each user's UUID
  — the same identity as their VLESS accounts. ✅
- **`hysteriaSettings`**: `version: 2` (required), `udpIdleTimeout` (2–600 s,
  default 60), `masquerade` (`type`: empty/`404` — the default —, `file` with
  `dir`, `proxy` with `url`/`rewriteHost`/`insecure`, or `string` with
  `content`/`headers`/`statusCode`). ✅
- **Congestion, bandwidth and port hopping moved.** `congestion`, `up`, `down`,
  `udphop` in `hysteriaSettings` only log a warning: they belong in
  `finalmask/quicParams` now (BBR profile, Brutal up/down, UDP hop). ✅
- **Obfuscation** (`salamander`) is configured in `finalmask` (`udp` masks) —
  the panel reads it from there for the subscription. ✅
- **Certificates are re-read from disk every hour** when given as files
  (`transport/internet/tls/config.go`: 3600 s unless `ocspStapling` sets
  another interval; skipped with `oneTimeLoading`). A renewal therefore needs
  no restart. ✅

## Where the certificate comes from — a panel trap ✅

When the panel prepares a node's config
(`get-prepared-config-with-users.handler.ts` → `processCertificates()`), it
reads `certificateFile` / `keyFile` **from the panel's own filesystem** and,
if they exist there, inlines the PEM — private key included — into the config
it sends the node. If the files do not exist on the panel, the error is
swallowed and the path is passed through; Xray on the node then reads it
locally.

So:
- **Cert files on the panel** → the key travels to every node of the profile
  inside its config (over the panel → node channel). One place to renew; the
  key is on the panel and in every config pushed.
- **Cert files only on the node** → mount them into the node container and use
  a path that does **not** exist on the panel; otherwise the panel silently
  inlines whatever lives at that path on its side.

**What the reference implementation does:** each node already holds a
certificate for its own name, issued and renewed by the web server's ACME
client into a Docker volume. That volume is mounted **read-only** into the node
container at `/etc/xray-tls` — a path the panel container does not have.
Angie's ACME client keeps each client's files in a sub-directory named after
the client: `<volume>/<acme_client name>/certificate.pem` and `private.key`
(✅ documented layout; 🔶 observed on a node, client name `letsencrypt`).
Renewal stays with the web server; Xray picks the new files up within the hour.

## Check the certificate BEFORE adding the inbound 🔶

Xray runs every inbound of a node in one process, and a TLS inbound whose
certificate it cannot read stops that process from starting. A Hysteria2
inbound with a wrong path therefore takes REALITY TCP and xHTTP down with it.

In the reference implementation, the playbook that enables Hysteria2 first
runs, on the node itself, a read-only
`docker exec <node container> sh -c 'test -s <dir>/certificate.pem && test -s <dir>/private.key'`
and stops before touching the panel if it fails. The first run in production
was stopped by exactly this — the node's stack predated the mount.

Rolling back one node: take the Hysteria2 inbound off the node's active
inbounds in the panel; Xray restarts without it.

## What the panel puts in the Mihomo entry ✅

`buildHysteria2Node`, `buildHysteria2QuicFields`, `buildHysteria2ObfsFields`,
`buildHysteria2TlsFields`:

| Mihomo key | From |
|---|---|
| `server`, `port` | the host's address and port |
| `password` | the user's UUID (with the host's VLESS route id, if set) |
| `udp: true` | always |
| `up` / `down` | `finalMask.quicParams.brutalUp` / `brutalDown` |
| `ports`, `hop-interval` | `finalMask.quicParams.udpHop` |
| `bbr-profile` | `finalMask.quicParams.bbrProfile` |
| `obfs: salamander`, `obfs-password` | `finalMask.udp` mask of type `salamander` |
| `sni`, `alpn` | the host's TLS settings |
| `client-fingerprint` | the host's fingerprint — **but Mihomo's `Hysteria2Option` has no such key** (v1.19.31), so it is ignored |
| `skip-cert-verify: true` | set when the host has `pinnedPeerCertSha256` |

⚠️ **Do not set `pinnedPeerCertSha256` on a Hysteria2 host for Mihomo clients
on panel 2.8.0.** The generator turns it into `skip-cert-verify: true` and does
not pass the pin (Mihomo's pin field is `fingerprint`), so certificate checking
is switched off with nothing in its place. Use a certificate that verifies
normally. The reference implementation's fleet audit fails on it.

## Masquerade

With the default (`404`), anything that speaks HTTP/3 to the port gets a bare
404. Pointing the masquerade at the decoy site the TCP side serves keeps the
node's story consistent.

`proxy` is Go's `httputil.ReverseProxy` over `http.DefaultTransport`
(`hub.go`, v26.6.27) ✅: it dials the URL's host, so it cannot reach a web
server that listens only on a unix socket — but it can reach the node's own
public name, where the TCP side (REALITY falling back to the web server)
answers with the decoy. The reference implementation uses
`https://<node name>` with `rewriteHost: true`; ❔ whether the hairpin works
on every provider — check with an HTTP/3 request from a browser (Chrome:
`--origin-to-force-quic-on=<name>:443`, no proxy), which should show the decoy
page with protocol `h3`. A `502` means the proxy could not reach it: fall back
to `404`.

## Measured 🔶

Reference implementation, one node, Mihomo client, delay tests (the method in
`mihomo.md`) on the same day as the xHTTP measurements:

| Entry | a few seconds apart | after 90 s idle |
|---|---|---|
| Hysteria2 | 0/30 failed, median 80 ms | 0/10 failed, median 86 ms |
| xHTTP (`grpc_pass`) | 0/60, median 114 ms | 1/20, median 115 ms |
| REALITY TCP | 0/30, median 92 ms | 0/10, median 87 ms |

A delay test is one round trip, not throughput; it says the path works and
does not stall after idle.

## Ports and the network

- Hysteria2 is QUIC: **UDP**. The host firewall needs its own rule; a firewall
  written for TCP 22/443 blocks it silently.
- **UDP 443 can hold one service.** xHTTP over HTTP/3 would also want it (the
  web server listening QUIC). Choose one, or run Hysteria2 on another UDP port —
  port hopping (`udpHop`) then helps against a single blocked port. 💡
- Some networks throttle or block UDP entirely; Hysteria2 complements the TCP
  entries, it does not replace them. 💡
- Anything on the node that intercepts UDP 443 (a DPI-evasion tool, a QUIC
  proxy) will fight the listener — enable such nodes last and check them
  separately. 💡
- ❔ quic-go asks the kernel for large UDP buffers and logs a warning when it
  cannot get them; if the node's log shows it, raise `net.core.rmem_max` /
  `wmem_max`.

## Adding it to a node, in order

1. The certificate is readable inside the node container at a path the panel
   does not have (check it — see above).
2. The firewall allows UDP 443.
3. The profile gains the inbound with a tag in the scheme
   (`XX-HYSTERIA2-QUIC-TLS`; in the reference implementation one more suffix
   in `playbooks/vars/inbound-tags.yml`), appended — never re-rendered — so the
   existing inbounds keep their identity.
4. The squads that already carry REALITY TCP gain it; the host is created
   (name, SNI, ALPN `h3`).
5. The node gains it in its active inbounds (the panel does not extend them
   when the profile grows).
6. One node, a Mihomo client, the delay-test measurement, before the fleet.
