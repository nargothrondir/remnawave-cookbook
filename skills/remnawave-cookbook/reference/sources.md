# Sources — where each fact comes from, and how to re-check it

The rule of this repository: a statement is only as good as the file it was
read from, at the version you run. Manuals say what a feature is *for* and
whether a scenario is supported; source at the pinned tag says what a call
actually *does*. Read both, in that order.

## Upstream repositories and the files this cookbook cites

| Project | Repository | Tag used | Files |
|---|---|---|---|
| Remnawave panel | `remnawave/backend` | `2.8.0` | `prisma/schema.prisma`; `src/common/helpers/xray-config/xray-config.validator.ts`; `src/modules/config-profiles/config-profile.service.ts`; `src/queue/_nodes/processors/start-all-nodes-by-profile.processor.ts`, `start-node.processor.ts`; `src/modules/subscription-template/resolve-proxy/resolve-proxy-config.service.ts`; `src/modules/subscription-template/generators/mihomo.generator.service.ts`; `src/common/utils/flow/get-vless-flow.ts`; `libs/contract/commands/**` |
| Remnawave node | `remnawave/node` | `2.8.0` | plugin code under `src/modules/_plugin` (no use of inbound ports found — 🔶 checked in that directory only) |
| Xray-core | `XTLS/Xray-core` | `v26.6.27` | `infra/conf/xray.go`; `infra/conf/transport_internet.go`; `transport/internet/splithttp/{config,hub}.go`; `common/protocol/http/headers.go`; `features/policy/policy.go` |
| Xray docs | `XTLS/Xray-docs-next` | `main` | `docs/config/transports/xhttp.md` → discussion #4113 |
| XHTTP design notes | `XTLS/Xray-core` discussion #4113 | — | web server advice (`grpc_pass`), XMUX rationale, logging advice |
| Xray examples | `XTLS/Xray-examples` | `main` | `VLESS-XHTTP3-Nginx/nginx.conf` |
| Xray-core issues | `XTLS/Xray-core` | — | #4446, #4716, #4894 (`grpc_pass` rough edges); #6444 (silently dead pooled connections); discussion #5822 (community advice to use `proxy_pass`) |
| Community example | `legiz-ru/my-remnawave` | `main` | README, xHTTP behind nginx — `grpc_pass` → `proxy_pass` on 2026-04-15 |
| Mihomo | `MetaCubeX/mihomo` | `v1.19.31` | `transport/xhttp/{config,client,reuse}.go`; `adapter/outbound/vless.go` |
| nginx | `nginx/nginx` | `master` | `src/http/modules/ngx_http_grpc_module.c` (request body is never buffered); `src/http/ngx_http_special_response.c` (stock error pages, when `error_page` applies); `src/http/ngx_http_core_module.c` (`ngx_http_named_location`: empty URI → 500) |
| Mozilla SSL guidelines | Mozilla's SSL Configuration Generator, its `guidelines/latest.json` | `6.0` | "intermediate": protocols, suites, groups (`X25519MLKEM768` first), server order off |
| Let's Encrypt | `letsencrypt.org` | — | "OCSP Service Has Reached End of Life" (2025-08-06) |
| Angie docs | `angie.software` | — | `server_tokens` (custom value: PRO only); Docker images (`ANGIE_LOAD_MODULES`) |
| Xray docs | `XTLS/Xray-docs-next` | `main` | `docs/en/config/transports/reality.md` (`target` with `X25519MLKEM768`; `limitFallback*` purpose) |
| Angie | `webserver-llc/angie` | `Angie-1.12.1` | `CHANGES` (HTTP/2 to backends arrived in 1.12.0) |

## Reading a file at a tag

```bash
gh api "repos/<owner>/<repo>/contents/<path>?ref=<tag>" --jq .content | base64 -d
```

Listing a tree to find where something moved between versions:

```bash
gh api "repos/<owner>/<repo>/git/trees/<tag>?recursive=1" --jq '.tree[].path' | grep -i <word>
```

## Caveats

- **Generated documentation (e.g. Context7) is built from `main`,** not from
  the tag you run, and may answer for a neighbouring topic (asked about xHTTP
  behind nginx, it returned the gRPC transport's advice). Use it to find where
  to look, never as the verdict.
- **Release notes describe the current release.** A pinned fleet is not on it.
- **Upstream issues are evidence of behaviour, not of intent.** A closed issue
  may be fixed in a tag newer than yours.
- **Another AI's summary is not a source.** Ask it for the file and the tag; if
  it cannot give them, treat the claim as unverified.
