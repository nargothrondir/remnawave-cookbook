# Operations map

Task → what to run → what success looks like → where to look when it does not.
Commands for the reference implementation name its Semaphore templates; the
"by hand" column says what the same operation is in panel terms, for a fleet
without that pipeline.

| Task | Reference implementation | In panel terms | Success looks like |
|---|---|---|---|
| New node | Semaphore **Provision Node** (survey: address, node name, profile, country) | profile (create if missing) → node with the profile's inbounds → stack deploy | the run's final smoke test connects the way a client does |
| Add xHTTP to a node | **Enable xHTTP** (node name, profile, country) | append inbound → squads → host → node `activeInbounds` → `XHTTP_PATH` on the stack | `added now: xhttp`, `hosts created: xhttp`, `now also serves 1 added inbound(s)`, `xHTTP on … DEPLOYED` |
| Re-run the same (idempotency) | **Enable xHTTP** again | — | `changed=0`; no deploy, no Xray restart |
| Switch the web-server hop for an A/B test | **Enable xHTTP** with CLI args `-e xhttp_upstream=http` (or `=grpc`) | set `XHTTP_UPSTREAM` on the node's stack, redeploy | `(upstream http) … DEPLOYED`; on the node the rendered config contains `proxy_request_buffering off` |
| Rename a profile's tags to the scheme | **Migrate inbound tags** (profile name) | see `reference/automation.md`, "Renaming tags safely" | `renamed … ; bindings restored`; a second run: `already on the … scheme, bindings intact` |
| Recover a migration that stopped mid-way | **Migrate inbound tags** with `-e 'migrate_restore=<printed snapshot>'` | re-bind squads, nodes, hosts from the snapshot | the final check passes |
| Apply a changed `angie.conf` | wait for the stack's scheduled sync (or deploy it), then `docker restart <angie>` on the node | — | the rendered file contains the change: `docker exec <angie> grep -c '<line>' /etc/angie/http.d/default.conf` → `1` |
| New Semaphore template appears | **Sync Templates**, then **Sync Survey** | — | `created: <name>`, then `added <fields>` |

## Before a fleet-wide change

- One node first, then the rest one at a time.
- Say in advance what users will notice: each profile change restarts Xray on
  that profile's nodes.
- Keep the snapshot or the previous value you would need to go back.

## Checking a node from its shell

```bash
docker exec <angie> grep -c 'grpc_pass unix:/dev/shm/xhttp.sock' /etc/angie/http.d/default.conf   # 1 = location rendered
ls -l /dev/shm/xhttp.sock                                                                          # srw-rw-rw- = inbound running
docker logs --since 10m <angie> 2>&1 | grep -c '\[error\]'                                         # errors on the hop
docker logs --since 10m <node> 2>&1 | grep -aiE 'xhttp|error' | tail -20                           # -a: the log has colour codes
```

Mask addresses before pasting any log anywhere:
`sed -E 's/[0-9]{1,3}(\.[0-9]{1,3}){3}/<IP>/g'`.
