# Mihomo (Clash.Meta) — the client side

Pinned to `MetaCubeX/mihomo` **v1.19.31**. Evidence marks: ✅ verified at that
tag · 🔶 partly · ❔ not verified. Sources: `sources.md`.

## What the panel sends

Remnawave 2.8.0 renders Mihomo subscriptions with a dedicated generator
(`mihomo.generator.service.ts`) ✅: VLESS with `packet-encoding: xudp`, the
`flow` only when it is `xtls-rprx-vision`, TLS or REALITY options from the
host, and for xHTTP an `xhttp-opts` block built from the inbound and the
host's `xhttpExtraParams`. An xHTTP entry looks like
`examples/mihomo-proxy.yaml`.

Mapping from the panel's `extra` to Mihomo keys ✅ (`XHTTP_FIELD_MAP`,
`XMUX_FIELD_MAP`):

| Panel (`xhttpExtraParams`) | Mihomo `xhttp-opts` |
|---|---|
| `xPaddingBytes` | `x-padding-bytes` |
| `noGRPCHeader` | `no-grpc-header` |
| `scMaxEachPostBytes` / `scMinPostsIntervalMs` / `scStreamUpServerSecs` | `sc-max-each-post-bytes` / `sc-min-posts-interval-ms` / `sc-stream-up-server-secs` |
| `xmux.maxConcurrency` / `maxConnections` / `cMaxReuseTimes` / `hMaxRequestTimes` / `hMaxReusableSecs` / `hKeepAlivePeriod` | `reuse-settings.max-concurrency` / `max-connections` / `c-max-reuse-times` / `h-max-request-times` / `h-max-reusable-secs` / `h-keep-alive-period` |
| `downloadSettings` | `download-settings` |

`noSSEHeader` is server-only and has no Mihomo counterpart.

## Mode selection ✅

`transport/xhttp/config.go`, `EffectiveMode`: an explicit `mode` is used as is;
`auto` (or empty) becomes

- over REALITY: `stream-one`, or `stream-up` when `download-settings` is set;
- otherwise (plain TLS): **`packet-up`**.

So an xHTTP-over-TLS entry runs packet-up — which is also the mode that
survives a web server in front most easily.

Defaults when unset ✅: `sc-max-each-post-bytes` 1000000,
`sc-min-posts-interval-ms` 30, `sc-max-buffered-posts` 30,
`sc-stream-up-server-secs` 20-80.

## `reuse-settings` is not optional ✅

`transport/xhttp/client.go`: the reuse manager is created only when
`ReuseConfig` is non-nil; `adapter/outbound/vless.go` builds a new HTTP
transport on every call otherwise. Without `reuse-settings`, **every proxied
connection opens a new TCP + TLS connection to the node** — slow, and many
more handshakes on the wire. Unlike the Xray client, Mihomo has no built-in
XMUX default (all zero), so the subscription must carry one. The values the
Xray client uses when its block is empty are a sound start:

```yaml
reuse-settings:
  max-concurrency: "16-32"
  max-connections: 0
  c-max-reuse-times: 0
  h-max-request-times: "600-900"     # below nginx's 1000 requests per connection
  h-max-reusable-secs: "1800-3000"   # below nginx's 1 h per connection
  h-keep-alive-period: 0
```

## HTTP version ✅

`NewTransport`: `alpn: [h3]` → HTTP/3 (QUIC); `alpn: [http/1.1]` → HTTP/1.1;
anything else → HTTP/2. HTTP/3 needs something listening on UDP 443 (see
`growth.md`).

## Measuring from the client

Mihomo's external controller answers
`GET /proxies/<name>/delay?timeout=<ms>&url=<url>` with `{"delay": <ms>}` or an
error. A loop of these — some a few seconds apart, some after a pause longer
than the web server's `keepalive_timeout` — separates "slow" from "fails after
idle", and is the way to compare two server configurations on the same entry.
Keep the controller secret out of scripts; prompt for it.

## Known differences from other clients

- Stash output from the panel skips xHTTP entirely ✅ (panel generator).
- The legacy Clash generator marks `xhttp` and `hysteria` unsupported ✅.
