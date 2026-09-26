# Checking a fleet: `validate.py` offline, the fleet audit live

Two tools, one set of invariants.

| | `validate.py` (this repository) | fleet audit (reference implementation) |
|---|---|---|
| Input | an exported profile (or all of them) + the rendered web config | the live panel, stack manager and secret store |
| Needs | Python 3, nothing else | the automation host's credentials |
| Sees | what is written in the configs | also bindings: squads, nodes, hosts, whether nodes are on, stack variables |
| For | anyone reproducing this architecture | the fleet it was written from |

## `validate.py`

```bash
# 1. Export: one profile, or all of them (tags are checked for panel-wide uniqueness)
curl -s -H "Authorization: Bearer $TOKEN" https://panel.example.com/api/config-profiles > profiles.json
# 2. The RENDERED web config, from inside the web server's container
docker exec <angie> cat /etc/angie/http.d/default.conf > angie.conf
# 3. Check
python validate.py profiles.json angie.conf
```

Keep both files out of any repository: the export holds REALITY private keys
and the xHTTP path.

Exit code `0` = no errors (warnings allowed), `1` = errors, `2` = input
unreadable. Each line is `LEVEL ID: message`.

### What each finding means

| ID | Level | Meaning |
|---|---|---|
| `TAG-MISSING` / `TAG-COMMA` / `TAG-DUPLICATE` | error | the panel would reject the config |
| `TAG-NOT-UNIQUE` | error | two profiles share a tag; tags are unique panel-wide |
| `TAG-SCHEME` | note | outside the `<CC>-<PROTOCOL>-…` scheme — fine, but never rename by hand |
| `REALITY-PORT` | error | REALITY not on 443 |
| `REALITY-DEST-MISSING` / `REALITY-SERVERNAMES` / `REALITY-PRIVATEKEY` | error | REALITY cannot work |
| `REALITY-SHORTID` / `REALITY-SHORTID-ODD` | error / warn | a shortId must be hex, ≤ 16 characters, even length |
| `REALITY-XVER` | warn | a local `dest` without `xver` — the decoy sees no client addresses |
| `REALITY-SHOW` | warn | debug output on in production |
| `XHTTP-NOT-SOCKET` | note | xHTTP not on a socket — the web-server checks do not apply |
| `XHTTP-SECURITY` | warn | TLS on the socket inbound; here the web server terminates TLS |
| `XHTTP-PORT` | warn | no `port` — the panel's host form will have an empty required field |
| `XHTTP-PATH-MISSING` | error | no path |
| `XHTTP-TRUSTED-XFF` / `…-SHAPE` | warn | no trusted header / values look like addresses (in v26.6.27 they are header names) |
| `XHTTP-NOSSE` | note | `noSSEHeader` set without a stream-one problem to solve |
| `WEB-TEMPLATE` | error | the template was passed instead of the rendered file |
| `WEB-NO-DECOY-LISTENER` | error | nothing listens on REALITY's `dest` socket |
| `WEB-PROXY-PROTOCOL` | error | `xver` and the listener's `proxy_protocol` disagree — every handshake breaks |
| `WEB-SERVER-NAME` | error | no decoy server block for REALITY's `serverNames` |
| `WEB-NO-XHTTP-LOCATION` | error | no location for the inbound's path (normalised to `/…/`) |
| `XHTTP-NO-UPSTREAM` / `XHTTP-SOCKET-MISMATCH` | error | the location does not reach the inbound's socket |
| `XHTTP-PROXY-BUFFERING` | error | `proxy_pass` without `proxy_request_buffering off` |
| `XHTTP-TRUSTED-HEADER` / `XHTTP-XFF-HEADER` | error | the trusted marker or `X-Forwarded-For` is not set — addresses lost, or forgeable |
| `XHTTP-ACCESS-LOG` | warn | the xHTTP path is logged |
| `XHTTP-BODY-SIZE` | warn | body limit not 0 |
| `XHTTP-READ-TIMEOUT` | warn | read timeout at or below ~330 s (the default is 60 s; the XTLS example's 315 s cut live streams) |

What it cannot see: whether an inbound is in a squad, active on a node,
published by a host, or whether a node is switched on. That needs the live
audit.

## The fleet audit

A read-only playbook in the reference implementation, run from Semaphore as
**Audit fleet**: every profile's tags and inbound shape, every scheme inbound's
squad, node and host, every host's port / security layer / xmux, every node on
and on its profile, and whether the node stack's `XHTTP_PATH` matches whether
the node serves xHTTP. Profiles deliberately left on old tags are listed in the
inventory and reported as warnings. It changes nothing (`changed=0`).

(Arriving with stage 4; this page describes its contract.)
