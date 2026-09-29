---
name: delay-probe
description: >-
  Use to measure how a proxy entry behaves from a real Mihomo (Clash.Meta)
  client — "the delay test sometimes fails", "it hangs after a pause", "is
  grpc_pass or proxy_pass better", "is the new protocol stable" — and to
  compare two server configurations on the same entry. Runs the plugin's
  mihomo-probe.ps1 (delay tests through Mihomo's controller: a warm burst,
  then probes after idle gaps) and reads the numbers: which phase fails, how
  to run an A/B fairly, when a difference is real. Triggers on: delay test,
  latency, пинг в клиенте, "fails after idle", A/B test, compare upstreams,
  measure Hysteria2 / xHTTP / REALITY.
---

# delay-probe — measure from the client

A delay test is one HTTP request through the entry (Mihomo's
`GET /proxies/{name}/delay`). It says whether the path works and how long one
round trip takes — not throughput. Run it from the machine where the client
runs.

## Run it

`mihomo-probe.ps1` (PowerShell 7; on the Bash tool's `PATH` while this plugin
is enabled, otherwise `${CLAUDE_PLUGIN_ROOT}/bin/mihomo-probe.ps1`).

```
pwsh -File mihomo-probe.ps1 -List -Match "xHTTP"                 # exact entry names, with their type
pwsh -File mihomo-probe.ps1 -Proxy "<entry>" -Label <what the server runs now>
pwsh -File mihomo-probe.ps1 -Proxy "<entry>" -BurstProbes 3 -IdleProbes 0   # 10-second smoke run
```

- **Controller:** a Windows named pipe whose name contains `mihomo` is found
  automatically — Clash Verge-family clients use one. Otherwise pass
  `-Controller http://127.0.0.1:9090`. `-NoSecret` when the controller has
  none; else the secret is prompted for and never stored.
- **Default run:** 30 probes 3 s apart, then 10 probes each after 90 s of
  silence — about 17 minutes. It waits between probes without printing a
  prompt.
- **Output:** one line per probe, a CSV `mihomo-probe-<label>-<time>.csv` in
  the current directory, and a summary per phase (probes, failed, median,
  p90).
- Entry names can identify a fleet: keep the CSV and the output out of
  anything public.

## Read it

| What you see | What it points to |
|---|---|
| failures in the **burst** | the path itself: blocked, throttled, misconfigured — go to `../remnawave-cookbook/diagnostics.md` |
| failures **only after idle**, none in the burst | a pooled connection that died while unused and is reused once more before the client notices. xHTTP with `reuse-settings` does this; an entry that dials fresh per request (REALITY TCP) does not — see `../remnawave-cookbook/diagnostics.md`, "The client" |
| median fine, p90 far above it | occasional slow handshakes or retransmits on the path, not a configuration fault |
| everything fails with `Timeout` right after a server change | the change is not applied yet, or broke the entry — check the server first |

A reference point, measured on one node of the reference implementation, one
client, same day (after 90 s idle, failures / probes):

| Entry | burst | after idle |
|---|---|---|
| Hysteria2 | 0/30, median 80 ms | 0/10, median 86 ms |
| REALITY TCP | 0/30, median 92 ms | 0/10, median 87 ms |
| xHTTP, `grpc_pass` | 0/60, median 114 ms | 1/20 |
| xHTTP, `proxy_pass` | 0/60, median 114 ms | 6/20 |

## Compare two configurations fairly (A/B)

1. **One variable, one node.** Switch only what you compare (for example
   `XHTTP_UPSTREAM=grpc|http`), on one node, and label each run with it.
2. **Back to back.** Run A, switch, wait a minute for the server to settle,
   run B. Runs hours apart compare the network at two times, not two
   configurations. Repeat the pair at least once.
3. **A control.** Measure another entry on the same node (REALITY TCP) in the
   same window: if it fails too, the cause is the client's network, not the
   configuration.
4. **Is the difference real?** Few after-idle probes decide little. Fisher's
   exact test on the after-idle counts, for example 1/20 against 6/20:

   ```
   python -c "from math import comb; a,n,b,m=1,20,6,20; t=a+b; N=n+m; p=[comb(t,k)*comb(N-t,n-k)/comb(N,n) for k in range(t+1)]; print(sum(x for x in p if x<=p[a]+1e-12))"
   ```

   That example gives p ≈ 0.09: suggestive, not proof. For a stronger answer,
   raise `-IdleProbes` (100 is about 2.5 hours) rather than repeating short
   runs.
5. **Decide on the numbers,** and write down both the counts and the
   p-value next to the decision.
