# Changelog

What each plugin version brings. Installed copies update only when the
version in `.claude-plugin/plugin.json` changes, so every change to `skills/`,
`agents/` or `bin/` comes with a new version and a section here (CI checks
both). Patch: text and fixes; minor: a new skill, agent or script.

## 0.2.2 — 2026-09-30

Snippets, read at the pinned panel version.

- `remnawave-2.8.md`, "Snippets": what they are, where the panel expands them,
  the silent drop of a missing name, no restart on change, the computed-config
  endpoint to see the result; what 3.x adds (`sync`, root-level merge).
- `validate.py --snippets <GET /api/snippets export>`: `SNIPPET-MISSING`
  (error), `SNIPPET-ROOT`, `SNIPPET-BALANCER` (warnings), `SNIPPET-UNCHECKED`
  (note).
- `growth.md`: snippets as an option, not used in the reference fleet.

## 0.2.1 — 2026-09-29

The cookbook catches up with the fleet audit it documents.

- `validate.py` checks the Hysteria2 inbound: `HY2-VERSION`, `HY2-NETWORK`,
  `HY2-TLS`, `HY2-CERT-INLINE` (errors), `HY2-PORT`, `HY2-MOVED-KEYS`
  (warnings), `HY2-MASQUERADE` (note). The example profile carries the
  inbound that runs.
- `audit.md`: every check of the fleet audit, by area and level, and what the
  offline validator cannot see.
- `diagnostics.md`: "Fleet audit findings" — each audit message to its cause
  and fix; Hysteria2 taking a node down, and `skip-cert-verify` in its Mihomo
  entry.
- Hysteria2 runs on the whole fleet (`hysteria2.md`, `growth.md`).

## 0.2.0 — 2026-09-29

The cookbook becomes a toolset.

- Skill `edge-check` with `bin/edge-check`: probe a node the way a scanner
  sees it — TLS version and group, certificate, headers, the 404 page, every
  error page the web server writes itself, a Host naming no server.
- Skill `delay-probe` with `bin/mihomo-probe.ps1`: delay tests from the Mihomo
  client, burst versus after-idle, and a fair A/B with Fisher's exact test.
- Skill `config-review`: `validate.py` on a profile export and the rendered
  web config, each finding mapped to its fix.
- Agent `pinned-source-checker`: settles a claim about Xray, Remnawave,
  Mihomo, Angie or nginx from source at a version tag, quotes marked verbatim
  or not.
- Reference: Angie as REALITY target — TLS profile (Mozilla intermediate 6.0,
  `X25519MLKEM768`), `Server: nginx` through headers-more, the decoy block
  line by line, stock nginx error pages and the named-location trap;
  `validate.py` finding `WEB-NAMED-ERROR-PAGE`.

## 0.1.0 — 2026-09-26

The reference skill: architecture, invariants and verified versions;
Remnawave 2.8, Xray v26.6.27, Angie, Mihomo, automation, Hysteria2 and growth
pages; diagnostics, operations, `validate.py` with tests, the audit guide;
entry points for Codex (`AGENTS.md`) and ChatGPT (a one-file bundle).
