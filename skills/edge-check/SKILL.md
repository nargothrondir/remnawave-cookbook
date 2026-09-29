---
name: edge-check
description: >-
  Use to check a REALITY self-steal node from the outside — "does this node
  still look like a plain nginx website?" — after changing its web-server
  (Angie/nginx) config, after a redeploy, or when a node is suspected of
  standing out. Runs the plugin's edge-check script (TLS version and group,
  certificate, Server header, HSTS / Alt-Svc, the 404 page, every error page
  the web server writes itself, a Host naming no server) and reads its
  PASS / FAIL lines back to causes and fixes. Triggers on: "check the node",
  "проверь ноду", "does the node look like nginx", "Angie in the error page",
  edge check, decoy check, after an angie.conf change.
---

# edge-check — does the node look like a plain nginx site?

A read-only probe, the way a scanner sees the node: plain HTTPS requests and
one TLS handshake. It does not log in anywhere and changes nothing.

## Run it

The script is `edge-check` (on the Bash tool's `PATH` while this plugin is
enabled; otherwise `${CLAUDE_PLUGIN_ROOT}/bin/edge-check`).

| Where | Command | What it sees |
|---|---|---|
| Any machine | `edge-check <node name>` | the node from the internet, through DNS |
| On the node | `edge-check <node name> --resolve 127.0.0.1` | the same, entering through REALITY on the node itself — no DNS, no network path in between |

`<node name>` is the node's own name: REALITY `serverNames`, the name its
certificate is issued for. Exit status 1 means at least one check failed.

**The output names the node.** Keep it out of issues, pull requests, commit
messages and anything else public; summarise by check name instead.

## Read it

| Line | FAIL / WARN means | Go to |
|---|---|---|
| `TLS version` | the target does not speak TLS 1.3 — REALITY needs it | `../remnawave-cookbook/reference/angie.md` → "TLS" |
| `TLS 1.3 group` (INFO) | shows what a client negotiated; `X25519MLKEM768` needs OpenSSL 3.5+ on the server and a client that offers it (Windows' Schannel-based curl and openssl builds may not) | same |
| `certificate` | the certificate is not valid for the name — the node is unusable while health checks stay green | `../remnawave-cookbook/reference/angie.md` → "The decoy server block" |
| `front page` | the decoy does not answer 2xx/3xx | `../remnawave-cookbook/diagnostics.md` → "The node and the web server" |
| `Server header` WARN | the header names a rarer server than nginx | `../remnawave-cookbook/reference/angie.md` → "Server identity" |
| `404 page` | wrong status, or the web server's own page with another name | `../remnawave-cookbook/reference/angie.md` → "The decoy server block" (`error_page 404`) |
| `400` … `412` with a signature other than nginx | the web server wrote its own error page and signed it — that code is missing from the stock-error list, or the change is not applied yet (a config-file-only change needs a container restart) | `../remnawave-cookbook/reference/angie.md` → "Error pages"; `../remnawave-cookbook/diagnostics.md` |
| `400 broken URL` with status 500 | an `error_page` points to a named location (`@…`) | `../remnawave-cookbook/diagnostics.md` → "A broken URL gets 500" |
| `foreign Host` WARN | a request whose Host names no server got an answer instead of a closed connection | `../remnawave-cookbook/reference/angie.md` → catch-all `return 444` |
| any `SKIP` | a local tool is missing (openssl, or curl without HTTP/2) — run from a machine that has it, or on the node | — |

## After a fix

A config-file-only change to a templated Angie applies on container restart
(`../remnawave-cookbook/reference/angie.md`, "The `-templated` image renders
with gomplate"). Run `edge-check` again on one node before the rest; all
checks PASS is the expected state of a node built from
`../remnawave-cookbook/examples/angie.conf`.
