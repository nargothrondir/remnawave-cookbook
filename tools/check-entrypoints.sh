#!/usr/bin/env bash
# The skill has several doors — SKILL.md for Claude, AGENTS.md for Codex and
# others, a built bundle for ChatGPT — and one body of content behind them.
# This fails when a door and the body drift apart:
#   [1] every skill path named in AGENTS.md exists;
#   [2] every content page is listed in BOTH SKILL.md and AGENTS.md;
#   [3] every relative Markdown link in the repository resolves;
#   [4] the bundle builds and contains every page.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
SKILL=skills/remnawave-cookbook
fail=0
err() { echo "  ::error::$*"; fail=1; }

echo "[1] paths named in AGENTS.md exist"
while IFS= read -r p; do
  p=${p%/}
  [ -e "$p" ] || err "AGENTS.md names $p, which does not exist"
done < <(grep -oE "$SKILL/[A-Za-z0-9._/-]+" AGENTS.md | sort -u)

echo "[2] every page is reachable from both entry points"
pages=$(cd "$SKILL" && ls reference/*.md operations.md diagnostics.md audit.md)
for p in $pages; do
  grep -qF "\`$p\`" "$SKILL/SKILL.md" || err "SKILL.md does not list $p"
  grep -qF "$SKILL/$p" AGENTS.md || err "AGENTS.md does not list $SKILL/$p"
done

echo "[3] relative links resolve"
while IFS= read -r md; do
  dir=$(dirname "$md")
  while IFS= read -r link; do
    target=${link%%#*}
    [ -n "$target" ] || continue
    [ -e "$dir/$target" ] || err "$md links to $link, which does not exist"
  done < <(grep -oE '\]\([^)]+\)' "$md" | sed -E 's/^\]\(//; s/\)$//' | grep -vE '^(https?:|mailto:|#)' || true)
done < <(git ls-files '*.md')

echo "[4] the bundle builds and carries every page"
tmp=$(mktemp)
bash tools/build-chatgpt-bundle.sh "$tmp" >/dev/null
for p in SKILL.md $pages; do
  grep -qF "<!-- file: $SKILL/$p -->" "$tmp" || err "bundle is missing $SKILL/$p"
done
rm -f "$tmp"

if [ "$fail" = 1 ]; then echo "FAILED: the entry points and the content drifted apart."; exit 1; fi
echo "OK: every entry point reaches every page."
