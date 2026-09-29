# Diagnostics — symptom → cause → check → fix

Every entry comes from a real incident on the reference fleet, with the
identifying details removed.

## Panel and automation

**A node is switched off after a profile change or a tag migration.**
- Cause: the panel switches off (and detaches) a node that serves no inbound
  when the profile's nodes restart (`remnawave-2.8.md`). A rename or a lost
  activation left the node with none for a moment.
- Check: node shows disabled, `activeConfigProfileUuid` empty or restored.
- Fix: restore its inbounds, then `POST /api/nodes/{uuid}/actions/enable`.
  Automations that rename must do this themselves.

**A new protocol's subscription entry exists but never connects; a check
reports "no node".**
- Cause: the inbound is in the profile, a squad and a host, but not in the
  node's `activeInbounds` — typically after a hand rename, which drops the
  activation by cascade.
- Check: the node's active inbounds; on the node, the inbound's socket
  (`ls -l /dev/shm/xhttp.sock`) is missing.
- Fix: add it to the node's `activeInbounds` (current + missing).

**Squad, node and host lost their binding after someone renamed a tag in the
UI.**
- Cause: tag = identity; rename = delete + create.
- Fix: re-bind squads, nodes, hosts to the new uuid; switch nodes back on if
  they were switched off. Better: never rename by hand.

**The host form in the UI shows an empty, required Port for an xHTTP host.**
- Cause: the form fills the port from the inbound; a socket inbound had none.
- Fix: give the inbound `"port": 443` (Xray ignores it for a socket).

**Every panel call from the automation is UNREACHABLE in a fraction of a
second, output censored.**
- Cause seen: a delegated task connected to a host that does not exist
  (templated `ansible_host` rendered for the task host — `automation.md`).
- Check: re-run with `-vvv`; read `ESTABLISH SSH CONNECTION FOR USER` and the
  host after it.
- Do not assume the network: the same SSH path worked from a diagnostic that
  built its host by literal name.

**A secret store `kv patch` fails with 403 at `sys/internal/ui/mounts/…`.**
- Cause: no token was passed to the CLI in the container (the path is a
  preflight, not the secret).
- Fix: pass the token explicitly (`-e BAO_TOKEN=…` / `VAULT_TOKEN`), read it
  with a hidden prompt, unset it afterwards. If it still fails, the policy
  lacks the preflight paths; a read-modify-write works without them.

## The node and the web server

**xHTTP entry fails; the node's web server logs `connect() to
unix:/dev/shm/xhttp.sock failed (2: No such file or directory)`.**
- Cause: the inbound is not running here (see "no node" above).

**A changed `angie.conf` "did nothing".**
- Cause: templated config renders at container start; a file-only change does
  not recreate the container.
- Fix: restart the container; verify with `grep -c` on the rendered file.

**Error log: `upstream timed out (110) while reading upstream` on the xHTTP
path, several streams of one connection at once.**
- Cause: the web server's read timeout fired on a stream Xray still considered
  alive (traffic in the other direction). The XTLS example's 315 s is too
  close to Xray's 300 s idle timeout.
- Fix: `grpc_read_timeout` / `grpc_send_timeout` 1 h; let Xray decide.

**Error log: `upstream prematurely closed connection` on the xHTTP path.**
- Usually Xray closing an idle connection; xHTTP sends no gRPC trailers, so the
  gRPC module records it as an error. Normal in small numbers.

**The web server's access log grows by megabytes in minutes.**
- Cause: packet-up = one POST per upload chunk, each padded in `Referer`.
- Fix: `access_log off` in the xHTTP location. It also stops recording the
  secret path and a timeline of user traffic.

**A broken URL (`GET /%`) gets 500 instead of 400.**
- Cause: an `error_page` for 400/414/494 points to a named location (`@…`).
  nginx empties the URI of a request it cannot parse and refuses a named
  location with an empty URI (`empty URI in redirect to named location`).
- Check: `validate.py` → `WEB-NAMED-ERROR-PAGE`; the error log line above.
- Fix: `error_page <code> /__error_page/<code>;` with an `internal` exact-match
  location (`reference/angie.md`, "Error pages").

**The header says `Server: nginx`, the error page body says `Angie`.**
- Cause: the code is not in the stock-error list, or the header was changed
  without the pages.
- Check: `curl -sk --http1.1 --resolve "<name>:443:127.0.0.1" "https://<name>/%" | tail -3`,
  and the other probes in `reference/angie.md`.
- Fix: add the code to the list.

**`angie -t` in CI fails on `unknown directive "more_set_headers"`.**
- Cause: CI renders without `ANGIE_LOAD_MODULES`, or with an image that lacks
  the module.
- Fix: take the image and `ANGIE_LOAD_MODULES` from the stack's compose file.

**The template does not render: `missing value for command`.**
- Cause: an empty pair of gomplate delimiters — often inside a `#` comment.
- Fix: describe the syntax in words in comments.

**`grep` on the node's container log prints `binary file matches`.**
- The log contains colour escape codes; use `grep -a`.

## The client

**Delay test sometimes shows no connection or hangs; browsing through the same
entry works.**
- 🔶 Measured, cause not proven. In the reference implementation (Mihomo,
  packet-up, one node): delay tests a few seconds apart never failed; after
  90 s of idle, xHTTP failed 1 in 20 with `grpc_pass` and 6 in 20 with
  `proxy_pass`, while REALITY TCP on the same node failed 0 in 10. So it is
  specific to xHTTP, happens only after idle, and is not caused by `grpc_pass`.
  The first candidate — the web server cutting half-idle streams — is fixed by
  the 1 h timeouts above.
- 💡 The explanation that fits: a pooled connection dies silently and the
  client still sends the next request on it. XHTTP's author describes this in
  XTLS/Xray-core#6444 (v26.6.27): a connection that carried no request for a
  while can be dropped by the network or a CDN without XHTTP noticing. The
  difference from REALITY TCP matches — its delay test dials a fresh
  connection each time, while xHTTP with `reuse-settings` reuses a pooled one.
  Mihomo notices a dead HTTP/2 connection only through its health check: after
  `h-keep-alive-period` without frames (0 → 45 s, `ChromeH2KeepAlivePeriod`,
  set as `HTTP2Config.SendPingTimeout` in `transport/xhttp/client.go` ✅) it
  sends a PING and drops the connection when no answer comes (timeout ❔ —
  Mihomo uses its own `net/http` fork).
- Check: a long run (100+ probes after idle) next to a REALITY TCP control; the
  failures' timing against the 45 s PING cycle is the next thing to look at.
  Accept it if it stays rare: the next request goes through.

**xHTTP is very slow on some sites, lots of new TLS connections to the node.**
- Cause: no `reuse-settings` in the Mihomo entry (the host's
  `xhttpExtraParams.xmux` missing) — a new connection per proxied connection.

## Before blaming the protocol

- Did the entry come from a fresh subscription? Old entries keep old tags,
  ports and paths.
- Is the other protocol on the same node working? If REALITY TCP works and xHTTP
  does not, the problem is on the xHTTP path (web server, socket, activation),
  not the node's reachability.
