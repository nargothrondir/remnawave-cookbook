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
# 3. Check (add --snippets snippets.json, from GET /api/snippets, if profiles use snippets)
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
| `HY2-VERSION` | error | `settings.version` or `hysteriaSettings.version` is not 2 — Xray refuses the whole config |
| `HY2-NETWORK` | error | a `hysteria` inbound on another transport — it does not start |
| `HY2-TLS` | error | no TLS — Xray does not start the listener, and the node loses every protocol with it |
| `HY2-CERT-INLINE` | error | certificate not given as `certificateFile` / `keyFile` — inline PEM travels in every config the panel pushes |
| `HY2-PORT` | warn | not on 443 — this architecture pairs UDP 443 with REALITY's TCP 443 |
| `HY2-MOVED-KEYS` | warn | `congestion` / `up` / `down` / `udphop` in `hysteriaSettings` — ignored with a warning; they live in `finalmask/quicParams` |
| `HY2-MASQUERADE` | note | default masquerade: a bare 404 to anything speaking HTTP/3 |
| `SNIPPET-MISSING` | error | a `{"snippet": …}` reference to a name the panel does not have — the element is dropped silently (`reference/remnawave-2.8.md`, "Snippets") |
| `SNIPPET-UNCHECKED` | note | a snippet reference, checked only with `--snippets` |
| `SNIPPET-ROOT` | warn | a root-level `snippets` key — panel 3.x only; 2.8.0 merges nothing |
| `SNIPPET-BALANCER` | warn | a snippet in `routing.balancers` with no `routing.rules` — panel 2.8.0 leaves it unexpanded |
| `WEB-TEMPLATE` | error | the template was passed instead of the rendered file |
| `WEB-NO-DECOY-LISTENER` | error | nothing listens on REALITY's `dest` socket |
| `WEB-PROXY-PROTOCOL` | error | `xver` and the listener's `proxy_protocol` disagree — every handshake breaks |
| `WEB-SERVER-NAME` | error | no decoy server block for REALITY's `serverNames` |
| `WEB-NO-XHTTP-LOCATION` | error | no location for the inbound's path (normalised to `/…/`) |
| `WEB-NAMED-ERROR-PAGE` | error | `error_page` for 400/414/494 points to a named location — a broken URL gets 500 (nginx refuses a named location with an empty URI) |
| `XHTTP-NO-UPSTREAM` / `XHTTP-SOCKET-MISMATCH` | error | the location does not reach the inbound's socket |
| `XHTTP-PROXY-BUFFERING` | error | `proxy_pass` without `proxy_request_buffering off` |
| `XHTTP-TRUSTED-HEADER` / `XHTTP-XFF-HEADER` | error | the trusted marker or `X-Forwarded-For` is not set — addresses lost, or forgeable |
| `XHTTP-ACCESS-LOG` | warn | the xHTTP path is logged |
| `XHTTP-BODY-SIZE` | warn | body limit not 0 |
| `XHTTP-READ-TIMEOUT` | warn | read timeout at or below ~330 s (the default is 60 s; the XTLS example's 315 s cut live streams) |

What it cannot see: whether an inbound is in a squad, active on a node,
published by a host, how that host is set, or whether a node is switched on.
Nor whether a certificate path given as a file exists on the panel — if it
does, the panel inlines the PEM itself (`reference/hysteria2.md`). That needs
the live audit.

## The fleet audit

A read-only playbook in the reference implementation, run from Semaphore as
**Audit fleet**. It reads the panel (profiles, squads, hosts, nodes) and the
stack manager (each node's stack variables), changes nothing (`changed=0`),
and fails the run on any error. Warnings do not fail it.

It looks at every REALITY TCP, xHTTP and Hysteria2 inbound in every profile:

| Area | Checked | Level |
|---|---|---|
| Profile | tag in the `<CC>-<PROTOCOL>-…` scheme | error; warning for profiles or nodes listed as legacy |
| Profile, xHTTP | listens on the socket the web server passes to; has a `port`; `trustedXForwardedFor` holds `X-Real-IP` | error; missing port a warning |
| Profile, Hysteria2 | `security: tls`; certificate as `certificateFile` / `keyFile` | error |
| Bindings | the inbound is in a squad, active on a node, published by a host | error |
| Hosts | port 443 | error |
| Hosts, xHTTP | `securityLayer` TLS; an `xhttpExtraParams.xmux` block | error |
| Hosts, Hysteria2 | ALPN contains `h3`; no `pinnedPeerCertSha256` | error |
| Nodes | switched on; attached to a profile | error |
| Nodes | connected to the panel right now | warning |
| Stacks | a node serving xHTTP has `XHTTP_PATH` in its stack | error |
| Stacks | a node not serving xHTTP has none; the node has a stack at all | warning |

Where it overlaps with `validate.py` — the inbound's shape — the audit is
stricter: it knows the one socket path the fleet uses, and a missing trusted
header is an error there, a warning here. What each failure means and how to fix it: `diagnostics.md`, "Fleet audit
findings".

Source: [`playbooks/audit-fleet.yml`](https://github.com/nargothrondir/ansible-playbooks/blob/main/playbooks/audit-fleet.yml)
in the reference implementation. To reproduce it elsewhere, the same checks
are four GETs (`/api/config-profiles`, `/api/internal-squads`, `/api/hosts`,
`/api/nodes`) plus your stack manager's environment per node.
