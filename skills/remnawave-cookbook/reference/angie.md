# Angie (or nginx) — the decoy site and the xHTTP hop

Evidence marks: ✅ verified in the named source · 🔶 partly / observed in
operation · ❔ not verified · 💡 hypothesis. Sources: `sources.md`.

Angie is an nginx fork; everything here applies to nginx unless noted.

## The `-templated` image renders with gomplate ✅

The `-templated` image runs **gomplate** over `/etc/angie/templates/` into
`/etc/angie/` **at container start**. Template syntax is
`{{ .Env.NAME }}` or `{{ getenv "NAME" "default" }}` — not `${NAME}`. Angie's
own `$variables` are untouched, since gomplate only reacts to `{{ }}`.

Mount your config into the templates input directory, not its final path:
`./angie.conf:/etc/angie/templates/http.d/default.conf:ro`.

**A config-file-only change does not reach a running container.** The deploy
writes the new file, `docker compose up` sees an unchanged service definition
and leaves the container running — with the old rendered config. 🔶 (observed)
Restart the container (`docker restart <angie>`); `angie -s reload` re-reads
the stale rendered file. A change to the service definition (an environment
variable) recreates the container and re-renders.

`test.Fail "message"` in a template aborts the render: use it to refuse
invalid values rather than silently falling back. ✅ (CI render of a bogus
value fails with the message)

## The decoy server block

```nginx
server {
    server_name node.example.com;                 # = REALITY serverNames
    listen unix:/dev/shm/nginx.sock ssl proxy_protocol;
    http2 on;
    # certificate for node.example.com (ACME, DNS-01 — no port 80 needed)
    root /var/www/html;
}
server {                                           # any other SNI: refuse
    listen unix:/dev/shm/nginx.sock ssl proxy_protocol default_server;
    server_name _;
    ssl_reject_handshake on;
}
```

- `proxy_protocol` on the listener is required: REALITY with `xver: 1` sends a
  PROXY header first, and the client address is then `$proxy_protocol_addr`.
- `http2 on` — the xHTTP client speaks HTTP/2 over this TLS.
- The certificate must be for the exact name in REALITY's `serverNames` and the
  subscription host's SNI; a mismatch makes the node unusable while every
  health check stays green.

## The xHTTP location

```nginx
location /<secret-path>/ {
    access_log off;
    client_max_body_size 0;
    client_body_timeout 5m;
    grpc_read_timeout 1h;
    grpc_send_timeout 1h;
    grpc_set_header X-Real-IP $proxy_protocol_addr;
    grpc_set_header X-Forwarded-For $proxy_protocol_addr;
    grpc_pass unix:/dev/shm/xhttp.sock;
}
```

Each line, and why:

| Line | Why | Evidence |
|---|---|---|
| `grpc_pass unix:…` | speaks HTTP/2 cleartext to the socket and **never buffers the request body** — every xHTTP mode passes | ✅ `ngx_http_grpc_module.c`: `r->request_body_no_buffering = 1`; ✅ #4113: "for Nginx, `grpc_pass` is recommended" |
| `client_max_body_size 0` | a packet-up POST is up to 1 000 000 bytes, right at the 1m default | ✅ Xray default `scMaxEachPostBytes` |
| `grpc_*_timeout 1h` | Xray closes idle connections at 300 s watching both directions; the web server watches one stream. At 315 s (the XTLS example) it cut live streams: `upstream timed out (110) while reading upstream` | ✅ Xray `policy.go`; 🔶 observed |
| `X-Real-IP` + `X-Forwarded-For` from `$proxy_protocol_addr` | Xray trusts `X-Forwarded-For` only when a header listed in `trustedXForwardedFor` is present; set and overwrite both so a client cannot forge them | ✅ Xray `headers.go` |
| `access_log off` | in packet-up every upload chunk is its own POST, each with 100–1000 bytes of padding in `Referer`: ~900 bytes a line, ~1 MB in three minutes of one client. Each line also records the secret path and a timeline of the user's traffic | ✅ #4113 advises not logging them; 🔶 measured |

The path must start and end with `/` (Xray normalises it that way) and must be
treated as a secret: it is the one request a node answers differently from the
decoy site. Keep it out of git; inject it (`XHTTP_PATH`) at deploy time.

Render the location only when the path is set, so the change can reach the
whole fleet while enabling xHTTP stays a per-node decision.

## `grpc_pass` or `proxy_pass`

The hop runs inside the node; a censor sees the same HTTPS either way. The
question is only whether the web server passes the stream faithfully.

| | `grpc_pass` | `proxy_pass` (defaults) | `proxy_pass` + `proxy_request_buffering off` |
|---|---|---|---|
| packet-up | ✅ | works, but each POST is read whole first; > `client_body_buffer_size` spills to disk | ✅ |
| stream-up | ✅ | ❌ endless body, never forwarded | ✅ |
| stream-one | ✅ | ❌ | ❔ |
| Log noise | `upstream prematurely closed connection` when Xray ends a stream on its own idle timeout (xHTTP sends no gRPC trailers) | none | none |
| Author's advice (#4113) | recommended | "if it does not pass Nginx, change `proxy_pass` to `grpc_pass`" | not discussed |

Response buffering is not the issue: Xray sends `X-Accel-Buffering: no`, which
nginx honours per response. ✅

Known rough edges of `grpc_pass` — all on the HTTP/2 hop between the web
server and Xray, so `proxy_pass` over HTTP/1.1 cannot have them:

- `protocol error: received DATA after END_STREAM` with packet-up
  (XTLS/Xray-core#4894, root cause not found); ❔ whether it affects users.
- `upstream sent too large http2 frame` with split upload/download
  (XTLS/Xray-core#4716).
- `http2: frame too large` (XTLS/Xray-core#4446): the author suspected the
  server not honouring the client's `SETTINGS_MAX_FRAME_SIZE`; that reporter's
  case went away with a different client fingerprint.

### Why many setups now use `proxy_pass` (checked 2026-09)

Upstream has not changed its advice: #4113 still recommends `grpc_pass`, the
official `XTLS/Xray-examples` (`VLESS-XHTTP3-Nginx/nginx.conf`) still uses it,
and the Xray documentation (`transports/xhttp.md`) does not mention nginx at
all. The move to `proxy_pass` is a community one:

- `legiz-ru/my-remnawave`, the most copied Remnawave xHTTP-behind-nginx
  example, replaced `grpc_pass` with `proxy_pass` on 2026-04-15 (commit
  "update xhttp example"), with no reason given. Its new block carries WebSocket
  `Upgrade`/`Connection` headers and no `proxy_request_buffering off` — the
  shape of a generic reverse-proxy template rather than one written for xHTTP.
- Answers in upstream discussions (e.g. XTLS/Xray-core discussion #5822,
  2026-03) suggest `proxy_pass` to people hitting `grpc_pass` errors; these are
  community replies, not the maintainers'.

The reasons that hold up:

1. **Clients that run packet-up do not need `grpc_pass`.** Mihomo and most
   mobile clients pick packet-up over TLS (see `mihomo.md`) — ordinary POSTs
   and one long GET, which HTTP/1.1 carries fine.
2. **The rough edges above exist only with `grpc_pass`.** Whoever hit one once
   switched and had no reason to come back.
3. **Familiarity:** `proxy_*` is what everyone already writes for websites.

The reason against: clients on the Xray core pick **stream-up** in `auto` mode
over HTTP/2. That needs a streaming request body; `proxy_pass` carries it only
with `proxy_request_buffering off`, and stream-one not reliably — which is why
the author recommends `grpc_pass`.

**Measured in the reference implementation** (one node, Mihomo client,
packet-up, delay tests after 90 s idle, two runs each, same day): `grpc_pass`
failed 1 of 20, `proxy_pass` (the variant below) 6 of 20; no failures in either
during active use; latency the same. Fisher's exact test p≈0.09 — suggestive,
not proof, but nothing favours `proxy_pass`. The reference implementation stays
on `grpc_pass` and keeps the switch for the day one of the rough edges shows up.

A fair comparison is by measurement, per node: render one block or the other
from an environment variable (`XHTTP_UPSTREAM=grpc|http`), switch one node,
and compare delay-test failures and error-log counts (see `mihomo.md` for the
client side). If you run `proxy_pass`, the variant is:

```nginx
proxy_http_version 1.1;
proxy_request_buffering off;   # the line that makes proxy_pass fit xHTTP at all
proxy_buffering off;
proxy_read_timeout 1h;
proxy_send_timeout 1h;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $proxy_protocol_addr;
proxy_set_header X-Forwarded-For $proxy_protocol_addr;
proxy_pass http://unix:/dev/shm/xhttp.sock;
```

Examples copied from WebSocket setups add `Upgrade`/`Connection` headers; xHTTP
does not switch protocols and does not need them.

HTTP/2 to backends (`proxy_http_version 2`) arrived in Angie 1.12.0 ✅
(`CHANGES`); whether it speaks cleartext HTTP/2 to a unix socket is ❔.

## Reading the error log

| Line | Meaning |
|---|---|
| `upstream prematurely closed connection while reading upstream … grpc://unix:/dev/shm/xhttp.sock` | Xray ended a stream the gRPC module still read — typically Xray's own 300 s idle close. Normal in small numbers |
| `upstream timed out (110: Operation timed out) while reading upstream` | the web server's read timeout fired before Xray's idle logic — raise `grpc_read_timeout` |
| `connect() to unix:/dev/shm/xhttp.sock failed (2: No such file or directory)` | the xHTTP inbound is not running on this node — not in the profile, or not active on the node |

💡 Hypothesis, weakened by measurement: the web server closes idle HTTP/2
client connections after `keepalive_timeout` (75 s by default) while the
client keeps them for reuse for 30–50 minutes, so a first request after a pause
lands on a dead connection. Delay tests after 90 s of idle failed 1 in 20 on
`grpc_pass` — a deterministic close would fail nearly all of them. See
`diagnostics.md` for the explanation that fits the numbers better.
