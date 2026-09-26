# Architecture

Evidence marks: ✅ verified in the named source · 🔶 partly verified ·
❔ not verified. Sources: `sources.md`.

## Components per node

| Component | Runs as | Listens on | Role |
|---|---|---|---|
| Remnawave node (Xray inside) | container, host network | `:443/tcp` (REALITY inbound); unix socket for xHTTP; node API port | serves users; receives its config from the panel |
| Angie (or nginx) | container, host network, `-templated` image | `unix:/dev/shm/nginx.sock` (`ssl proxy_protocol`) | decoy website with its own certificate; hands the secret xHTTP path to Xray |
| ACME helper | container, loopback only | `127.0.0.1` | answers DNS-01 challenges for Angie — no inbound port 80 needed |

`/dev/shm` is shared between the node and Angie containers, which is how both
unix sockets are reachable across them.

## Path of one connection

1. The client opens TCP to `:443` and sends a TLS ClientHello.
2. **Xray's REALITY inbound** inspects it.
   - A REALITY client (authenticated in the handshake) is handled by Xray: the
     VLESS user is served directly.
   - Anything else — a browser, a scanner, an xHTTP client doing ordinary TLS —
     is forwarded byte for byte to REALITY's `dest`, here Angie's socket, with a
     PROXY protocol header (`xver: 1`) carrying the client's address. ✅
3. **Angie terminates TLS** with its own certificate for the node's name, so a
   probe sees a normal site with a valid chain. It matches the SNI against its
   `server_name`; an SNI it does not serve gets `ssl_reject_handshake`.
4. On the **secret xHTTP path**, Angie passes the request to the xHTTP inbound
   over `unix:/dev/shm/xhttp.sock` (`grpc_pass`, HTTP/2 cleartext). Every other
   path is the decoy site.
5. The **xHTTP inbound** (VLESS, no TLS) serves the user. VLESS itself does not
   encrypt (`decryption: none`); confidentiality comes from the TLS session
   between the client and Angie. The Angie → Xray hop is cleartext but never
   leaves the machine.

## What each client type sees

| | REALITY TCP | xHTTP |
|---|---|---|
| Client's TLS peer | Xray (REALITY) | Angie |
| Certificate check | REALITY key, not a CA chain | ordinary CA chain for the node's name |
| On the wire | TLS 1.3 to the node's name | HTTPS (HTTP/2) to the node's name |
| Through a CDN | no | possible (`growth.md`) |

## Ports

| Port | Exposure | Purpose |
|---|---|---|
| `443/tcp` | public | the only user-facing port |
| node API (Remnawave node) | private network only | panel → node control; never public |
| SSH | public and/or private network, per your policy | administration and automation; keep the automation port distinct from any mesh-provided SSH that intercepts port 22 |

Nothing else needs to be open for users. ACME uses DNS-01, so port 80 stays
closed. UDP 443 is free — the natural home for Hysteria2 or xHTTP over HTTP/3,
but only one of them (`growth.md`, `hysteria2.md`).

## Control plane

- The **panel** holds the Xray configuration as *config profiles* and pushes it
  to nodes; nodes are reached on their API port over a private network
  (a WireGuard-based mesh in the reference implementation).
- **Everything the fleet depends on is created through APIs, idempotently** —
  panel objects, Dockhand stacks and their environment, secrets from the secret
  store. See `automation.md` and the reference
  implementation: `ansible-playbooks` and `docker-stacks` (linked in README).
