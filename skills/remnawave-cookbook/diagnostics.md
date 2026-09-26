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

**`grep` on the node's container log prints `binary file matches`.**
- The log contains colour escape codes; use `grep -a`.

## The client

**Delay test sometimes shows no connection or hangs; browsing through the same
entry works.**
- 💡 Open question. Candidates in order: the web server cutting half-idle
  streams (fixed by the 1 h timeouts above); idle HTTP/2 connections closed by
  the web server's `keepalive_timeout` while the client still reuses them; an
  artefact of `grpc_pass` with packet-up (XTLS/Xray-core#4894).
- Check: measure (see `reference/mihomo.md`, "Measuring from the client"):
  failures right after a pause longer than 75 s point at keep-alive; failures
  spread evenly point elsewhere. Compare `grpc_pass` and `proxy_pass` on one
  node before changing the fleet.

**xHTTP is very slow on some sites, lots of new TLS connections to the node.**
- Cause: no `reuse-settings` in the Mihomo entry (the host's
  `xhttpExtraParams.xmux` missing) — a new connection per proxied connection.

## Before blaming the protocol

- Did the entry come from a fresh subscription? Old entries keep old tags,
  ports and paths.
- Is the other protocol on the same node working? If REALITY TCP works and xHTTP
  does not, the problem is on the xHTTP path (web server, socket, activation),
  not the node's reachability.
