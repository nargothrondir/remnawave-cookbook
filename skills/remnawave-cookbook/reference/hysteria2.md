# Hysteria2 — the next protocol, checked before it is built

Status in the reference implementation: **planned, not running.** Everything
below is read from source at the pinned versions; nothing here has carried user
traffic yet. Evidence marks: ✅ verified at the tag · 🔶 partly · ❔ not
verified · 💡 design consideration.

## Support across the stack

| Layer | Version | Support | Evidence |
|---|---|---|---|
| Xray server | v26.6.27 | inbound `protocol: "hysteria"`, `version: 2` only; transport `network: "hysteria"` + `hysteriaSettings` | ✅ `infra/conf/hysteria.go`, `infra/conf/transport_internet.go` |
| Remnawave panel | 2.8.0 | `hysteria` allowed as protocol and network; users added with `auth` = the user's VLESS UUID | ✅ `xray-config.validator.ts` (`ALLOWED_PROTOCOLS`, `addUsersToInbound`) |
| Subscription for Mihomo | 2.8.0 | `type: hysteria2`, rendered by `buildHysteria2Node` | ✅ `mihomo.generator.service.ts` |
| Mihomo client | v1.19.31 | `type: hysteria2` | ✅ `adapter/outbound/hysteria2.go` |

## Server side (Xray v26.6.27)

- **TLS is mandatory.** The listener refuses to start without it
  (`tls config is nil`, `transport/internet/hysteria/hub.go`) and offers ALPN
  `h3`. So the inbound needs `streamSettings.security: "tls"` with a real
  certificate for the name clients connect to. ✅
- **Users.** `settings.clients[].auth`; the panel fills it with each user's UUID
  — the same identity as their VLESS accounts. ✅
- **`hysteriaSettings`**: `version: 2` (required), `udpIdleTimeout` (2–600 s,
  default 60), `masquerade` (`type`: empty/`404` — the default —, `file`,
  `proxy` with `url`/`rewriteHost`/`insecure`, or `string` with
  `content`/`headers`/`statusCode`). ✅
- **Congestion, bandwidth and port hopping moved.** `congestion`, `up`, `down`,
  `udphop` in `hysteriaSettings` only log a warning: they belong in
  `finalmask/quicParams` now (BBR profile, Brutal up/down, UDP hop). ✅
- **Obfuscation** (`salamander`) is configured in `finalmask` (`udp` masks) —
  the panel reads it from there for the subscription. ✅

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

💡 In the reference implementation each node already holds a certificate for
its own name, issued by Angie's ACME client into a Docker volume. Mounting that
volume read-only into the node container would let Hysteria2 reuse it, with
renewal handled by Angie. The file layout inside Angie's ACME storage is ❔
not verified — find it before designing around it.

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
normally.

## Ports and the network

- Hysteria2 is QUIC: **UDP**. In the reference implementation the host firewall
  opens TCP 22 and 443 only; UDP needs its own rule.
- **UDP 443 can hold one service.** xHTTP over HTTP/3 would also want it (the
  web server listening QUIC). Choose one for UDP 443, or run Hysteria2 on
  another UDP port — port hopping (`udpHop`) then helps against a single
  blocked port. 💡
- Some networks throttle or block UDP entirely; Hysteria2 complements the TCP
  entries, it does not replace them. 💡

## Masquerade 💡

With the default (`404`), anything that speaks HTTP/3 to the port gets a bare
404. Pointing the masquerade at the same decoy site the TCP side serves keeps
the node's story consistent; whether `proxy` can reach a web server that
listens only on a unix socket is ❔ — it may need a loopback listener.

## Before building it

1. Decide UDP 443 or another UDP port (and whether xHTTP H3 is ever wanted).
2. Decide where the certificate lives (panel vs node; see the trap above).
3. Firewall rule for UDP.
4. Profile: inbound with a tag in the scheme (e.g. `XX-HYSTERIA2-QUIC-TLS`;
   in the reference implementation that is one more suffix in
   `playbooks/vars/inbound-tags.yml`), `security: tls`, `finalmask` as
   needed; host with the node's name as address and SNI; squad; node.
5. One node, a Mihomo client, and the delay-test measurement from
   `mihomo.md`, before the fleet.
