# Remnawave 2.8 — panel model and API contracts

Pinned to backend **2.8.0** (`remnawave/backend`, tag `2.8.0`). Evidence marks:
✅ verified in the file named · 🔶 partly · ❔ not verified. Paths are relative
to that repository.

## The model

| Object | What it is | Identity used by automation |
|---|---|---|
| **Config profile** | an Xray config (inbounds, outbounds, routing) | its name (unique) |
| **Inbound** | one inbound of a profile, stored as its own row | its **tag** |
| **Host** | one entry in the client's subscription, bound to exactly one inbound | the inbound it points at (`inbound.configProfileInboundUuid`) — never its remark, which people rename |
| **Internal squad** | which users see which inbounds | its name |
| **Node** | a server running a profile's inbounds (`activeInbounds`) | its address |

Two protocols on one node = two inbounds = two hosts.

## Inbound identity and what a rename does ✅

- `prisma/schema.prisma`, `model ConfigProfileInbounds`: `@@unique([tag])` —
  **a tag is unique across the whole panel**, not per profile. Two profiles
  cannot both have `VLESS-TCP-REALITY`; put something profile-specific in the
  tag (the reference implementation uses a country-code prefix,
  `XX-VLESS-TCP-REALITY`, `XX-VLESS-XHTTP-TLS`).
- `src/modules/config-profiles/config-profile.service.ts`, `syncInbounds`: on a
  config update, old and new inbounds are matched by **tag + protocol**. An
  inbound whose tag changed is deleted and a new one (new uuid) created.
- `schema.prisma` relations on that delete:
  - `InternalSquadInbounds` → `onDelete: Cascade` (squad membership gone),
  - `ConfigProfileInboundsToNodes` → `onDelete: Cascade` (node activation gone),
  - `Hosts.configProfileInboundUuid` → `onDelete: SetNull` (host orphaned, kept).
- Nothing else references an inbound: per-user traffic history
  (`NodesUserUsageHistory`) is keyed by node and user.

**So:** never rename a tag in the UI. A migration records each inbound's
squads, nodes and hosts first, PATCHes the config with only the tags changed,
then re-binds squads (users), nodes (serving) and hosts (subscription) to the
new uuids.

## Updating a profile ✅

- `libs/contract/commands/config-profiles/update-config-profile.command.ts`:
  `PATCH /api/config-profiles` with `{uuid, config}` — the whole config.
- `config-profile.service.ts`, `updateConfigProfile`: after saving, calls
  `startAllNodesByProfile` — **every node of the profile restarts Xray**.
- The config validator
  (`src/common/helpers/xray-config/xray-config.validator.ts`):
  - allowed protocols include `vless`, `trojan`, `shadowsocks`, `hysteria`;
  - allowed networks include `tcp`, `raw`, `xhttp`, `ws`, `grpc`,
    `httpupgrade`, `kcp`, `hysteria`;
  - tags must exist, be unique within the config and contain no `,`;
  - **`port` is optional** (`parsePort` returns `null`) — a unix-socket inbound
    is accepted.
- New inbounds are **not** activated on existing nodes
  (`createManyConfigProfileInbounds` only inserts rows). Add them to each
  node's `activeInbounds` explicitly.

**Add, never rewrite:** build the PATCH body as the current config with new
inbounds appended — never re-render a template (that would mint new REALITY
keys) — and afterwards assert the existing inbounds kept their uuids.

## Nodes ✅

- `libs/contract/commands/nodes/update.command.ts`: `PATCH /api/nodes` accepts
  `configProfile: {activeConfigProfileUuid, activeInbounds: [uuid…]}` — the
  list replaces the node's set, so send current + missing. It has **no
  `isDisabled` field**.
- `src/queue/_nodes/processors/start-all-nodes-by-profile.processor.ts` (and
  `start-node.processor.ts`): a node with **zero active inbounds** is set
  `isDisabled: true` and `activeConfigProfileUuid: null`, then stopped. A tag
  migration can hit this: until the re-bind, a node whose inbounds were all
  renamed serves none. Whether the queued restart reaches it in that window is
  a race.
- Switching a node back on: `POST /api/nodes/{uuid}/actions/enable`
  (`libs/contract/api/controllers/nodes.ts`, `commands/nodes/actions/enable.command.ts`).
  Wait for any restart already queued before calling it.

## Hosts ✅

- `libs/contract/commands/hosts/create.command.ts`: `address` and **`port`
  are required on the host itself**; `remark` ≤ 40 characters; optional
  `sni`, `host`, `path`, `alpn`, `fingerprint`, `securityLayer`
  (`DEFAULT`/`TLS`/`NONE`), `xhttpExtraParams`, `isHidden`, `isDisabled`.
- `libs/contract/constants/hosts/alpn.ts`: `h3`, `h2`, `http/1.1`,
  `h2,http/1.1`, `h3,h2,http/1.1`, `h3,h2`.
- `src/modules/subscription-template/resolve-proxy/resolve-proxy-config.service.ts`:
  - the subscription's port is the **host's** port (`port: inputHost.port`);
  - `securityLayer: TLS` overrides the inbound's own `security` — how a
    no-TLS socket inbound is published as TLS;
  - for xHTTP, `path`, `host` and `extra` are the host's value when set, else
    the inbound's (`xhttpExtraParams` → `extra`).
- `libs/contract/commands/hosts/update.command.ts`: `PATCH /api/hosts` with
  `{uuid, inbound: {configProfileUuid, configProfileInboundUuid}}` re-points a
  host and leaves every other setting as it is.
- `schema.prisma`: `viewPosition` is an autoincrement — a new host lands at
  the end of the list, so it does not displace the first (default) entry in a
  client's selector group.
- The panel stores a host's remark exactly as given. A country flag has to be
  put in the remark by whoever creates it (🔶 checked in 2.8.0: the country
  emoji helper serves node statistics only).

## Squads ✅

- `PATCH /api/internal-squads` with `{uuid, inbounds: [uuid…]}` — the list
  **replaces** the squad's inbounds. Always send current + missing.
- A protocol added next to an existing one should join exactly the squads
  that already carry the existing inbound, so it reaches the same users.

## VLESS flow ✅

`src/common/utils/flow/get-vless-flow.ts`: `xtls-rprx-vision` is assigned only
to VLESS inbounds whose network is `tcp`/`raw` and security `reality`/`tls`
(or where the inbound sets it explicitly). An xHTTP inbound gets no flow.

## Subscription for Mihomo ✅

`src/modules/subscription-template/generators/mihomo.generator.service.ts`:
- renders xHTTP (`buildXhttpOpts`: `path`, `host`, `mode`, `headers`, the
  padding/session/seq fields, `reuse-settings` from `extra.xmux`,
  `download-settings` from `extra.downloadSettings`) and Hysteria2
  (`buildHysteria2Node`);
- Stash output skips xHTTP; the legacy Clash generator marks `xhttp` and
  `hysteria` as unsupported.

## Calling the API

- Requests without `X-Forwarded-For` and `X-Forwarded-Proto: https` are
  dropped when the panel is called directly rather than through its reverse
  proxy (🔶 observed; the panel's proxy-check middleware).
- Send numbers as numbers (`port: 443`, not `"443"`): the contracts are Zod
  schemas and reject strings.
