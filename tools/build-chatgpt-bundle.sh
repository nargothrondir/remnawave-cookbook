#!/usr/bin/env bash
# Build dist/remnawave-cookbook.md — the whole skill in one Markdown file, for
# assistants that cannot read the repository (a ChatGPT Project's files).
#
# Order: the router first (what to use when), then reference, operations,
# diagnostics, audit, examples. Every part is preceded by its path, so an
# answer can cite the file it came from. validate.py is not inlined: it is a
# program to run, not text to read — the bundle says where it lives.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
SKILL=skills/remnawave-cookbook
OUT=${1:-dist/remnawave-cookbook.md}
mkdir -p "$(dirname "$OUT")"

parts=("$SKILL/SKILL.md")
while IFS= read -r f; do parts+=("$f"); done < <(ls "$SKILL"/reference/*.md | sort)
parts+=("$SKILL/operations.md" "$SKILL/diagnostics.md" "$SKILL/audit.md")

{
  echo "# remnawave-cookbook — single-file bundle"
  echo
  echo "Built from commit $(git rev-parse --short HEAD). Source of truth:"
  echo "the repository's \`$SKILL/\`. Keep the evidence marks when you answer"
  echo "(✅ verified · 🔶 partly · ❔ not verified · 💡 hypothesis); the"
  echo "offline validator is \`$SKILL/validate.py\` in the repository."
  for f in "${parts[@]}"; do
    echo
    echo "---"
    echo
    echo "<!-- file: $f -->"
    echo
    # Drop the YAML front matter of SKILL.md; keep everything else verbatim.
    awk 'NR == 1 && /^---$/ { fm = 1; next } fm && /^---$/ { fm = 0; next } !fm' "$f"
  done
  for f in "$SKILL"/examples/*; do
    echo
    echo "---"
    echo
    echo "<!-- file: $f -->"
    echo
    case "$f" in
      *.json) lang=json ;; *.yaml|*.yml) lang=yaml ;; *.conf) lang=nginx ;; *) lang= ;;
    esac
    echo "\`\`\`$lang"
    cat "$f"
    echo "\`\`\`"
  done
} > "$OUT"

echo "wrote $OUT ($(wc -l < "$OUT") lines, ${#parts[@]} pages + examples)"
