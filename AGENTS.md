# AGENTS.md — remnawave-cookbook

Entry point for agents that read `AGENTS.md` (OpenAI Codex and others). The
content lives in `skills/remnawave-cookbook/`; this file only routes to it, so
there is one source of truth.

## What this is

A cookbook for a Remnawave fleet built as VLESS + REALITY (TCP, Vision) on
:443 with a self-steal decoy site behind Angie/nginx on a unix socket, plus
VLESS over xHTTP on the same port through that web server, for Mihomo clients,
automated through the panel API. Facts are pinned to Remnawave 2.8.0, Xray
v26.6.27, Mihomo v1.19.31 and Angie 1.12, and each cites the upstream file it
was read from.

## How to answer

1. Start from `skills/remnawave-cookbook/SKILL.md` — the architecture, the
   invariants and the table of where to look.
2. Answer from the matching file below, keeping its evidence mark
   (✅ verified · 🔶 partly · ❔ not verified · 💡 hypothesis). Do not fill
   gaps from memory; say what is unverified and name the upstream file to read
   (`reference/sources.md`).
3. For something broken, go symptom-first through `diagnostics.md` and propose
   its check before any fix. A 💡 hypothesis calls for a measurement, not a
   change.
4. To review a config, run
   `python skills/remnawave-cookbook/validate.py <profile.json> [rendered angie.conf]`
   and explain its findings with `audit.md`.
5. Never put IP addresses, real domains, provider or node names into anything
   you write here; examples use `example.com` and documentation ranges.

## Files

| Topic | File |
|---|---|
| Router: architecture, invariants, versions | `skills/remnawave-cookbook/SKILL.md` |
| Traffic paths and ports | `skills/remnawave-cookbook/reference/architecture.md` |
| Remnawave 2.8 panel model and API contracts | `skills/remnawave-cookbook/reference/remnawave-2.8.md` |
| Xray v26.6.27: REALITY on a socket, xHTTP, timeouts, trusted headers | `skills/remnawave-cookbook/reference/xray-v26.6.27.md` |
| Angie/nginx: decoy block, xHTTP location, grpc_pass vs proxy_pass | `skills/remnawave-cookbook/reference/angie.md` |
| Mihomo client | `skills/remnawave-cookbook/reference/mihomo.md` |
| Automation through the API | `skills/remnawave-cookbook/reference/automation.md` |
| Growth: protocols and combinations beyond what runs | `skills/remnawave-cookbook/reference/growth.md` |
| Hysteria2 in depth | `skills/remnawave-cookbook/reference/hysteria2.md` |
| Sources and how to re-check a fact | `skills/remnawave-cookbook/reference/sources.md` |
| Operations: task → what to run → success | `skills/remnawave-cookbook/operations.md` |
| Diagnostics: symptom → cause → check → fix | `skills/remnawave-cookbook/diagnostics.md` |
| Checking configs and the fleet | `skills/remnawave-cookbook/audit.md` |
| Offline validator | `skills/remnawave-cookbook/validate.py` |
| Examples (placeholders only) | `skills/remnawave-cookbook/examples/` |

## ChatGPT without repository access

ChatGPT in the browser does not read repositories. Build one file and add it to
a ChatGPT Project's files:

```bash
bash tools/build-chatgpt-bundle.sh      # writes dist/remnawave-cookbook.md
```

The same file is attached to every CI run as the `chatgpt-bundle` artifact.
