# remnawave-cookbook

**English** · [Русский](README.ru.md)

An agent skill (Claude Code plugin) for running a **Remnawave** fleet built as:

- **VLESS + REALITY (TCP, Vision)** on port 443, with a **self-steal decoy site**
  behind **Angie/nginx on a unix socket**;
- **VLESS over xHTTP on the same port 443**, handed to Xray by that web server on
  one secret path;
- **Mihomo (Clash.Meta)** clients;
- everything created through the **panel API**, idempotently.

It is a cookbook in both senses: general recipes and facts about the
protocols and combinations, and a reference implementation that runs them.

## What makes it different

- **Every fact is pinned to a version and cites its source file.** The stack
  moves fast and AI assistants answer confidently from memory; this skill
  answers from the code of Remnawave 2.8.0, Xray v26.6.27 and Mihomo v1.19.31,
  and marks anything it could not verify.
- **Written from a real fleet, then depersonalised.** No IP addresses, domains,
  provider or node names — enforced by CI, including a secret list of
  forbidden strings that never enters the repository.
- **Lessons that cost something.** Tag identity and the cascade a rename
  triggers, nodes the panel switches off by itself, why `grpc_pass` and not
  `proxy_pass` by default, why Mihomo needs `reuse-settings`.

## Status

All six stages of the plan are in:

- the router and the reference (architecture, Remnawave 2.8 API contracts,
  Xray v26.6.27, Angie, Mihomo, automation, sources);
- an operations map, diagnostics and examples;
- an offline validator with tests, and the live fleet audit in the reference
  implementation;
- entry points for other assistants;
- growth notes: a matrix of what else the stack can do (Hysteria2, xHTTP H3,
  split directions, CDN, WebSocket, gRPC) and a Hysteria2 page checked against
  source before it is built.

## Layout

```
.claude-plugin/              plugin and marketplace manifests
skills/remnawave-cookbook/
  SKILL.md                   router: architecture, invariants, verified versions
  reference/                 architecture · remnawave-2.8 · xray-v26.6.27 · angie · mihomo · automation · growth · hysteria2 · sources
  operations.md              task → what to run → what success looks like
  diagnostics.md             symptom → cause → check → fix
  examples/                  depersonalised profile, Angie blocks, Mihomo entries
  validate.py                offline check of a profile export + rendered web config (stdlib)
  audit.md                   how to run it, what each finding means; the live fleet audit
AGENTS.md                    entry point for Codex and other AGENTS.md readers
tests/                       one test per validator rule
tools/
  tells-guard.sh             nothing here may identify real infrastructure
  check-entrypoints.sh       every entry point reaches every page; links resolve
  check-versions.sh          documented versions = what the reference implementation pins
  build-chatgpt-bundle.sh    the whole skill as one Markdown file
```

## Install (Claude Code)

```
/plugin marketplace add nargothrondir/remnawave-cookbook
/plugin install remnawave-cookbook@remnawave-cookbook
```

Or copy `skills/remnawave-cookbook/` into `~/.claude/skills/` or
`<project>/.claude/skills/`.

## Other assistants

- **OpenAI Codex** and other tools that read `AGENTS.md`: clone the repository
  into (or next to) your project; `AGENTS.md` routes to the same content.
- **ChatGPT** (no repository access): run `bash tools/build-chatgpt-bundle.sh`,
  or download the `chatgpt-bundle` artifact from any CI run, and add
  `remnawave-cookbook.md` to a ChatGPT Project's files.

CI checks that all of them lead to the same pages, so no door goes stale.

## Reference implementation

The architecture described here runs from two public repositories:
[`ansible-playbooks`](https://github.com/nargothrondir/ansible-playbooks)
(provisioning and panel automation through the API) and
[`docker-stacks`](https://github.com/nargothrondir/docker-stacks) (the node
stack: Remnawave node, Angie, ACME helper).

## Acknowledgements

- **[Case211/skill-remnawave-xray](https://github.com/Case211/skill-remnawave-xray)** —
  thank you. The shape of this skill (a router over reference pages,
  symptom-driven diagnostics, an executable consistency check, entry points
  kept in sync) is inspired by that work. The text here was written anew from
  primary sources for a different architecture and version set; no text or code
  was copied, which is why this repository carries its own licence (MIT) while
  the original is AGPL-3.0.
- **[XTLS/Xray-core](https://github.com/XTLS/Xray-core)** and RPRX's
  [XHTTP: Beyond REALITY](https://github.com/XTLS/Xray-core/discussions/4113).
- **[Remnawave](https://github.com/remnawave)**,
  **[MetaCubeX/mihomo](https://github.com/MetaCubeX/mihomo)**, **Angie**.
- **[legiz-ru/my-remnawave](https://github.com/legiz-ru/my-remnawave)** — for
  the worked example of xHTTP through nginx with Remnawave.

## Disclaimer

Educational material about privacy and censorship-circumvention technology.
Use it within the law of your jurisdiction. Examples use placeholders
(`example.com`, documentation address ranges) and are templates, not configs
to run as they are.

## Licence

MIT — see [LICENSE](LICENSE).
