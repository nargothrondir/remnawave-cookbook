# Xray v26.6.27 — what this architecture relies on

Pinned to `XTLS/Xray-core` tag **v26.6.27** (the core bundled with Remnawave
node 2.8.0). Evidence marks: ✅ verified at that tag · 🔶 verified on `main`
or indirectly · ❔ not verified.

## REALITY with a self-steal decoy on a unix socket

- REALITY forwards any handshake it does not authenticate to `dest` byte for
  byte; with `xver: 1` it prepends a PROXY protocol v1 header carrying the
  client's address. The decoy web server must listen with `proxy_protocol`.
- `dest` can be a unix socket path (`/dev/shm/nginx.sock`), so the decoy needs
  no TCP port at all.
- `serverNames` = the name the decoy's certificate is issued for. If they
  disagree, the web server rejects the handshake it was handed and the node is
  unusable while every health check stays green.

## A socket listener ignores `port` ✅

`infra/conf/xray.go`, `InboundDetourConfig.Build`: when `listen` is an absolute
path (or `@abstract`), `PortList` is set to `nil`. `"listen": "/dev/shm/xhttp.sock,0666"`
(the `,0666` suffix sets the socket's mode) works with or without `port`.

## xHTTP (`network: "xhttp"`, a.k.a. splithttp)

The authoritative description is the protocol author's
[XHTTP: Beyond REALITY (Xray-core discussion #4113)](https://github.com/XTLS/Xray-core/discussions/4113);
the official docs page `docs/config/transports/xhttp.md` consists of a link to it.

**Configure only `path`** (plus `mode` if you must) — the author's first
advice. The defaults are already tuned:

| Setting | Side | Default | Evidence |
|---|---|---|---|
| `xPaddingBytes` | both | `100-1000` | 🔶 `transport/internet/splithttp/config.go` on main |
| `scMaxEachPostBytes` | both (client splits, server rejects larger with 413) | `1000000` | 🔶 main |
| `scMinPostsIntervalMs` | client | `30` | 🔶 main |
| `scMaxBufferedPosts` | server, per session | `30` | ✅ `GetNormalizedScMaxBufferedPosts` |
| `scStreamUpServerSecs` | server, stream-up only (keep-alive padding) | `20-80` | 🔶 main |
| `noSSEHeader` | server | `false` (download sends `Content-Type: text/event-stream`) | ✅ `hub.go` |

Server-side behaviour ✅ (`transport/internet/splithttp/hub.go`): the download
response always carries `X-Accel-Buffering: no` and `Cache-Control: no-store`,
so nginx/Angie do not buffer it; `text/event-stream` is added unless
`noSSEHeader`. The author suggests `noSSEHeader` only as a remedy for
stream-one trouble — leave it at the default unless you have that trouble.

Path normalisation ✅ (`splithttp/config.go`): the path always starts and ends
with `/`. A web-server `location` prefix must match that form.

**Modes.** The server accepts all three by default (`mode: auto`); a client in
`auto` picks one. The Xray client picks stream-up over TLS H2 and stream-one
over REALITY; **Mihomo picks packet-up over TLS** (see `mihomo.md`, later
stage). Behind a web server, packet-up survives almost anything; stream-up
needs the request body to be streamed (see `angie.md`, later stage).

**XMUX** — client-side connection reuse ✅ (`infra/conf/transport_internet.go`):
when the whole `xmux` block is empty the Xray client uses `maxConnections: 6`,
`hMaxRequestTimes: 600-900`, `hMaxReusableSecs: 1800-3000`;
`maxConnections` and `maxConcurrency` cannot both be set. The last two stay
below nginx's defaults (1000 requests and 1 hour per connection), so the
client retires a connection before the server closes it (#4113). **Mihomo has
no such default** — deliver `xmux` through the subscription.

## Client addresses behind a web server ✅

`common/protocol/http/headers.go`, `ApplyTrustedXForwardedFor`:
`X-Forwarded-For` is used only if `streamSettings.sockopt.trustedXForwardedFor`
lists **header names** and at least one of them is present on the request.
Otherwise the real remote address (the socket) is used and a warning is logged
for every request that carried `X-Forwarded-For`.

So: `"trustedXForwardedFor": ["X-Real-IP"]` on the inbound, and the web server
sets **and overwrites** both `X-Real-IP` and `X-Forwarded-For` from
`$proxy_protocol_addr`, so a client cannot forge them. Note: the semantics of
this field changed around the 26.6.x releases (earlier builds and some issues
describe CIDR values) — check it at your tag.

## Timeouts ✅

`features/policy/policy.go`, `SessionDefault`: `Handshake 60s`,
`ConnectionIdle 300s`, `UplinkOnly 1s`, `DownlinkOnly 1s`. Xray closes a proxied
connection after 300 s with no traffic in **either** direction.

A web server in front watches one HTTP stream at a time. If its read timeout is
close to 300 s, it cuts streams Xray still considers alive (a long upload whose
server answers only at the end). Set the web server's timeouts well above
300 s (the reference uses 1 h) and let Xray decide.

## Before upgrading past v26.6.27 ❔

- **REALITY `minClientVer`.** A newer default that refuses older clients is
  reported (sources disagree on v26.7.11 vs v26.7.28). In v26.6.27 the value is
  applied only when set (`infra/conf/transport_internet.go`); in later tags the
  REALITY config moved to `infra/conf/transport_security.go`. Find where the
  default is set before upgrading, and decide deliberately.
- **XMUX defaults are recent.** The empty-block default of `maxConnections: 6`
  is what v26.6.27 itself ships; upstream issue #6444 reports stream-up
  instability with v26.6.27 that v26.6.22 did not have, discussed in terms of
  that default. Re-read `infra/conf/transport_internet.go` at any new tag.
