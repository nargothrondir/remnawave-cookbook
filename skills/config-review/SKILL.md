---
name: config-review
description: >-
  Use before applying a change to a Remnawave config profile or to the node's
  web-server config (Angie/nginx in front of REALITY and xHTTP) — "review this
  profile", "is this angie.conf safe to merge", "check the inbound before I
  PATCH it" — and when a node misbehaves after such a change. Runs the
  cookbook's offline validate.py on an exported profile and the rendered web
  config, then maps every finding ID to its meaning and fix. Triggers on:
  config review, ревью конфига, validate.py, inbound / REALITY / xHTTP /
  Hysteria2 settings, error_page, grpc_pass, trustedXForwardedFor, before a merge or a
  panel update.
---

# config-review — check a profile and its web config before they go live

`validate.py` is offline and standard-library only: it reads files, sends
nothing anywhere, and checks the invariants this architecture depends on — in
the profile (tags, REALITY, xHTTP and Hysteria2 inbounds) and in the web server's config
(the decoy listener, `proxy_protocol`, `server_name`, the xHTTP location, error
pages).

## 1. Get the two inputs

| Input | How | Note |
|---|---|---|
| The profile(s) | the panel API `GET /api/config-profiles` (all profiles — tags are checked panel-wide), or one profile's `config` | holds REALITY private keys and the xHTTP path: keep the file local, never commit or paste it |
| The **rendered** web config | `docker exec <web server container> cat /etc/angie/http.d/default.conf` | not the template: template markers are refused (`WEB-TEMPLATE`). For a change not yet deployed, render it the way the stack's CI does |

The web config is optional; without it only the profile is checked.

## 2. Run it

```
python ${CLAUDE_PLUGIN_ROOT}/skills/remnawave-cookbook/validate.py <profiles.json> [rendered.conf]
```

Exit status `0` = no errors (warnings allowed), `1` = errors, `2` = unreadable
input. Each line is `LEVEL ID: message`.

## 3. Read it

Every ID, its level and meaning: `../remnawave-cookbook/audit.md`. The ones
that most often block a change:

| ID | Stop because | Fix in |
|---|---|---|
| `TAG-NOT-UNIQUE`, `TAG-DUPLICATE` | the panel rejects the config, or a rename re-creates the inbound and drops its squads, nodes and hosts | `../remnawave-cookbook/reference/remnawave-2.8.md` |
| `REALITY-*` errors | REALITY cannot work on this node | `../remnawave-cookbook/reference/xray-v26.6.27.md` |
| `WEB-PROXY-PROTOCOL` | `xver` and the listener disagree — every handshake breaks | `../remnawave-cookbook/reference/angie.md` → "The decoy server block" |
| `WEB-SERVER-NAME` | no decoy server for REALITY's `serverNames` | same |
| `WEB-NO-XHTTP-LOCATION`, `XHTTP-SOCKET-MISMATCH`, `XHTTP-NO-UPSTREAM` | xHTTP reaches nothing | `../remnawave-cookbook/reference/angie.md` → "The xHTTP location" |
| `XHTTP-PROXY-BUFFERING` | `proxy_pass` buffers the body; stream-up never passes | same → "`grpc_pass` or `proxy_pass`" |
| `XHTTP-TRUSTED-HEADER`, `XHTTP-XFF-HEADER` | client addresses are lost, or a client can forge them | same |
| `WEB-NAMED-ERROR-PAGE` | a broken URL gets 500 instead of 400 | `../remnawave-cookbook/reference/angie.md` → "Error pages" |
| `HY2-TLS`, `HY2-VERSION`, `HY2-NETWORK` | Xray refuses the inbound — and with it every protocol on the node | `../remnawave-cookbook/reference/hysteria2.md` |
| `HY2-CERT-INLINE` | the private key would travel in every config the panel pushes | same → "Where the certificate comes from" |

Warnings (`XHTTP-ACCESS-LOG`, `XHTTP-READ-TIMEOUT`, `XHTTP-BODY-SIZE`, …) do not
block, but each has a measured reason in `../remnawave-cookbook/reference/angie.md`
(the `HY2-*` ones in `../remnawave-cookbook/reference/hysteria2.md`).

## 4. After it is live

`validate.py` sees the files, not the node. Check the node itself with the
`edge-check` skill, and bindings (squads, nodes, hosts) and the hosts' settings (ALPN, pins, xmux)
with the panel API or a fleet audit (`../remnawave-cookbook/audit.md`).

Report findings by ID and file, never by pasting the inputs: they carry keys,
the xHTTP path and the node's name.
