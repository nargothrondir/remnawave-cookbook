#!/usr/bin/env bash
# Every fact in this skill is pinned to a version. When the reference
# implementation moves to another version, the facts have to be re-verified —
# so this fails as soon as the pins in docker-stacks and the table in SKILL.md
# disagree, instead of the skill quietly describing a version nobody runs.
#
# Compared:
#   Remnawave node — exact (ghcr.io/remnawave/node:<version>); it also fixes
#                    the bundled Xray, so a change here means re-reading the
#                    Xray page too;
#   Angie          — major.minor (docker.angie.software/angie:<x.y.z>-templated
#                    against "x.y.x" in the table); patch bumps are routine.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
URL=${DOCKER_STACKS_COMPOSE_URL:-https://raw.githubusercontent.com/nargothrondir/docker-stacks/main/remnanode/docker-compose.yml}
TABLE=skills/remnawave-cookbook/SKILL.md

compose=$(curl -fsSL "$URL")
pin_node=$(printf '%s\n' "$compose" | sed -nE 's#^\s*image:\s*ghcr\.io/remnawave/node:([0-9.]+).*#\1#p' | head -1)
pin_angie=$(printf '%s\n' "$compose" | sed -nE 's#^\s*image:\s*docker\.angie\.software/angie:([0-9]+\.[0-9]+)\.[0-9]+.*#\1#p' | head -1)

doc_node=$(sed -nE 's/^\| Remnawave node \| ([0-9.]+) \|.*/\1/p' "$TABLE" | head -1)
doc_angie=$(sed -nE 's/^\| Angie \| ([0-9]+\.[0-9]+)\.x.*/\1/p' "$TABLE" | head -1)

fail=0
check() { # name pinned documented
  if [ -z "$2" ] || [ -z "$3" ]; then
    echo "  ::error::$1: could not read the pin ('$2') or the table ('$3')"; fail=1
  elif [ "$2" != "$3" ]; then
    echo "  ::error::$1: docker-stacks pins $2, SKILL.md documents $3 — re-verify the facts for $2, then update the table"; fail=1
  else
    echo "  ok: $1 $2"
  fi
}
check "Remnawave node" "$pin_node" "$doc_node"
check "Angie" "$pin_angie" "$doc_angie"

if [ "$fail" = 1 ]; then echo "FAILED: the documented versions no longer match what runs."; exit 1; fi
echo "OK: documented versions match the reference implementation."
