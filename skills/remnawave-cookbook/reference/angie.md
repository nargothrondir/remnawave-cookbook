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

**gomplate parses its delimiters inside `#` comments too.** A comment such as
"template syntax is" followed by an empty pair of double braces is an empty
action and fails the render with `missing value for command`. ✅ (CI render)
Describe the syntax in words in comments.

Read every environment variable once, at the top of the file, into template
variables (`$node_name := getenv "NODE_NAME"`), check the required ones there
with `test.Fail`, and use the variables below. The inputs of the file are then
one short block instead of calls scattered through it; a variable declared at
the top is visible inside every later `if` and `range`.

## TLS — what every TCP client of the node is seen doing

With REALITY self-steal the web server is REALITY's target, and its TLS is
more than the decoy site's encryption:

- REALITY uses its target's handshake as camouflage. If the target supports
  `X25519MLKEM768`, REALITY clients that offer it use it too ✅ (Xray docs,
  REALITY `target`). Mihomo strips that group from its REALITY ClientHello
  unless `support-x25519mlkem768` is set ✅ (`component/tls/reality.go`,
  v1.19.31), so for Mihomo users REALITY stays on X25519 either way.
- xHTTP clients, browsers and probes end their TLS here.

So the aim is to look like an ordinary, current web server, and the profile is
the one most such servers are configured from — Mozilla "intermediate",
guidelines 6.0 ✅:

```nginx
ssl_protocols              TLSv1.2 TLSv1.3;
ssl_ecdh_curve             X25519MLKEM768:X25519:prime256v1:secp384r1;
ssl_ciphers                ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;
ssl_prefer_server_ciphers  off;
ssl_session_timeout        1d;
ssl_session_cache          shared:MozSSL:10m;
ssl_session_tickets        off;
```

- `X25519MLKEM768` needs OpenSSL 3.5 or newer; `angie -V` names the version
  the image was built and runs with. The Angie 1.12 images ship 3.5.x 🔶.
- Relative to the older 5.x profile: no `DHE-RSA-*` suites (they never apply
  without `ssl_dhparam` anyway) and `ssl_prefer_server_ciphers off`.
- No OCSP stapling: Let's Encrypt shut its OCSP service down on 2025-08-06 ✅
  and publishes revocation through CRLs only.
- Check it through REALITY, the way a visitor arrives:
  `echo | openssl s_client -connect 127.0.0.1:443 -servername <node name> 2>/dev/null | grep -E "Negotiated TLS1.3 group|Protocol"`
  should print `X25519MLKEM768` and `TLSv1.3` 🔶.

## Server identity — `Server: nginx` on Angie

`server_tokens off` removes the version from the `Server` header and from
error pages, but the open-source Angie cannot rename itself: a custom or empty
value needs Angie PRO ✅ (Angie docs, `server_tokens`). Angie is rare outside
Russia while nginx is the most common server there is, so "Server: Angie" on a
foreign VPS is a small, free signal 💡.

The headers-more module does it:

```nginx
more_set_headers  "Server: nginx";
```

- The `-templated` images ship the module; the image's own main-config
  template loads it when the `ANGIE_LOAD_MODULES` environment variable names
  it: `ANGIE_LOAD_MODULES=headers-more` ✅ (Angie docs, Docker). `load_module`
  cannot go in a file included inside `http {}`.
- The template that decides this is `/etc/angie/templates/angie.conf` in the
  image — not the `ANGIE_CONFIG_TEMPLATE` path its environment still names
  🔶 (observed in `1.12.2-templated`). The module key is the word after
  `has $modules` there.
- Validate the config in CI with the same image **and** the same
  `ANGIE_LOAD_MODULES`, or `angie -t` fails on the unknown directive — and a
  floating image tag validates a different Angie than production.
- The header alone is half of it: Angie's own error pages end in
  `<center>Angie</center>` — see "Error pages" below.

## The decoy server block

```nginx
server {
    listen       unix:/dev/shm/nginx.sock ssl proxy_protocol;
    server_name  node.example.com;                      # = REALITY serverNames
    http2        on;

    set_real_ip_from  unix:;
    real_ip_header    proxy_protocol;

    # certificate for node.example.com (ACME, DNS-01 — no port 80 needed)

    add_header  Strict-Transport-Security  "max-age=63072000"  always;
    add_header  Alt-Svc  'h3=":443"; ma=86400'  always;  # only if UDP 443 answers HTTP/3
    add_header  X-Robots-Tag  "noindex, nofollow, noarchive, nosnippet, noimageindex"  always;

    root   /var/www/html;
    index  index.html;

    error_page  404  /index.html;

    location / {
        try_files   $uri $uri/ =404;
        gzip        on;
        gzip_vary   on;
        gzip_types  text/css application/javascript application/json image/svg+xml;
    }
}
server {                                                # any other SNI: refuse
    listen       unix:/dev/shm/nginx.sock ssl proxy_protocol default_server;
    server_name  _;
    ssl_reject_handshake  on;
    return                444;
}
```

| Line | Why |
|---|---|
| `proxy_protocol` on the listener | REALITY with `xver: 1` sends a PROXY header first; without it every handshake breaks |
| `http2 on` | the xHTTP client speaks HTTP/2 over this TLS |
| `set_real_ip_from unix:` + `real_ip_header proxy_protocol` | every connection arrives over the unix socket, so the access log records `unix:` for every request. With these, `$remote_addr` is the client address from the PROXY header and the decoy's log shows who scans and probes the node ✅ (`unix:` is a documented value of the realip module). Users do not appear: REALITY traffic never reaches the web server, and the xHTTP location does not log |
| `Strict-Transport-Security` | what an HTTPS-only site sends (Mozilla: two years). A node behind REALITY has no port 80 to break |
| `Alt-Svc: h3` | only when UDP 443 really answers HTTP/3 — e.g. Hysteria2 whose masquerade serves this same site (`hysteria2.md`). The TCP and UDP sides then tell one story, and browsers reach the decoy over h3. A browser whose QUIC attempt fails falls back to TCP |
| `X-Robots-Tag` | keeps the decoy out of search engines |
| `error_page 404 /index.html` | an unknown path gets the site's own page, still status 404 — what many small sites do, instead of the web server's stock page. Works only if the site's assets use absolute paths (check the templates). Set on the server: an `error_page` in a location replaces every one inherited |
| `gzip` inside `location /` only | ordinary sites compress text. Never on the xHTTP location: compression buffers the stream |
| catch-all: `ssl_reject_handshake on` | a handshake for any other SNI is refused before a certificate is shown |
| catch-all: `return 444` | a request whose `Host` names no server lands here even after a handshake on the node's name; close without an answer. Checked: `curl -H "Host: example.com"` over the node's SNI gets no response 🔶 |

The certificate must be for the exact name in REALITY's `serverNames` and the
subscription host's SNI; a mismatch makes the node unusable while every health
check stays green.

## Error pages — nginx's own, never Angie's

Once the header says nginx, the body must too. Every error page the web server
writes itself — not the site's — ends in `<hr><center>Angie</center>` on
Angie. Anyone can reach them with a malformed request 🔶 (all checked on a
live node):

| Probe | Code |
|---|---|
| a broken URL (`GET /%`) | 400 |
| an oversized request line | 414 |
| an oversized header | 494 → answers 400 |
| `TRACE` | 405 |
| an unknown `Transfer-Encoding` | 501 |
| a `Range` past the end of a file | 416 |
| a failed `If-Match` | 412 |
| an unsupported HTTP version in the request line | 505 |

Answer each with nginx's stock page, byte for byte — same status line, CRLF
line ends, `<hr><center>nginx</center>`, `text/html`, no `ETag` or
`Last-Modified`. With gomplate, one `dict` and two `range`s keep it short:

```nginx
{{- $stock_errors := dict "400" "400 Bad Request" "403" "403 Forbidden" "405" "405 Not Allowed" "412" "412 Precondition Failed" "413" "413 Request Entity Too Large" "414" "414 Request-URI Too Large" "416" "416 Requested Range Not Satisfiable" "494" "400 Request Header Or Cookie Too Large" "500" "500 Internal Server Error" "501" "501 Not Implemented" "502" "502 Bad Gateway" "503" "503 Service Temporarily Unavailable" "504" "504 Gateway Time-out" "505" "505 HTTP Version Not Supported" }}

    # in the decoy server block:
{{- range $code, $status := $stock_errors }}
    error_page  {{ $code }}  /__error_page/{{ $code }};
{{- end }}
{{- range $code, $status := $stock_errors }}
    location = /__error_page/{{ $code }} { internal; default_type text/html; return {{ strings.Trunc 3 $status }} "<html>\r\n<head><title>{{ $status }}</title></head>\r\n<body>\r\n<center><h1>{{ $status }}</h1></center>\r\n<hr><center>nginx</center>\r\n</body>\r\n</html>\r\n"; }
{{- end }}
```

- The titles are nginx's (`src/http/ngx_http_special_response.c`) ✅. `494` is
  nginx's internal code for oversized headers; it answers `400` with its own
  title.
- Each location is a literal `return <code> "<body>"`, so the status never
  depends on how the redirect is resolved.
- ⚠️ **Redirect to an internal URI, never to a named location (`@…`).** For a
  request whose URI it cannot parse, nginx empties `r->uri`, and
  `ngx_http_named_location` refuses to enter a named location with an empty
  URI — it logs `empty URI in redirect to named location` and finalizes with
  **500** ✅ (`src/http/ngx_http_core_module.c`). With `@…` a broken URL went
  from the stock 400 to a 500 🔶 (observed); `TRACE`, whose URI is valid,
  worked — which is why the bug hides. An internal redirect to a real URI sets
  the URI first, so request-line errors, header errors and HTTP/2 are all
  covered. `validate.py` flags `WEB-NAMED-ERROR-PAGE`.
- Check the three stages on the node: `GET /%` over HTTP/1.1 (expect `400`), an
  oversized URL (expect the nginx tail), and `GET /%` over HTTP/2.

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
