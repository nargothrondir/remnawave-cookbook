#!/usr/bin/env bash
# Tag a commit as the plugin version it carries and publish a GitHub Release.
#
# Claude Code itself updates installed copies by the `version` in
# .claude-plugin/plugin.json and never reads tags or releases. The tag is for
# people: pinning a checkout (`claude plugin marketplace add <repo>#<tag>`),
# the `<plugin>--v<version>` convention that plugin dependencies resolve
# against, and seeing which commit a version was. The release carries that
# version's CHANGELOG.md section as its notes.
#
# Idempotent: a version that already has its tag is left alone, so CI can run
# this on every push to main and an old version can be tagged afterwards.
# The newest version (the one HEAD carries) is marked "latest"; an older one
# tagged afterwards is not.
#
# Usage: release.sh [--dry-run] <commit>
# Needs: git with the repository's history; gh authenticated (GH_TOKEN in CI).
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
export MSYS_NO_PATHCONV=1 # see check-version-bump.sh
if python3 -c 'pass' 2>/dev/null; then py=python3; else py=python; fi

dry=0
if [ "${1:-}" = "--dry-run" ]; then dry=1; shift; fi
ref=${1:?usage: release.sh [--dry-run] <commit>}
sha=$(git rev-parse --verify "$ref^{commit}")

manifest_at() { # <ref> <field> -> the field of plugin.json at that ref
  git show "$1:.claude-plugin/plugin.json" |
    "$py" -c 'import json, sys; print(json.load(sys.stdin)[sys.argv[1]])' "$2"
}

name=$(manifest_at "$sha" name)
version=$(manifest_at "$sha" version)
tag="$name--v$version"

if git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null; then
  echo "OK: $tag already exists; nothing to do."
  exit 0
fi

# The notes are the version's section of the CHANGELOG on this checkout, not
# at the commit: a section may have been written after the commit it describes.
notes=$(awk -v v="$version" '
  index($0, "## " v " ") == 1 || $0 == "## " v { on = 1; next }
  on && /^## / { exit }
  on && !started && /^[[:space:]]*$/ { next }
  on { started = 1; print }
' CHANGELOG.md)
if [ -z "$(printf '%s' "$notes" | tr -d '[:space:]')" ]; then
  echo "::error::CHANGELOG.md has no '## $version' section — nothing to publish as notes."
  exit 1
fi

latest=false
[ "$version" = "$(manifest_at HEAD version)" ] && latest=true

echo "Release $tag at ${sha:0:7} (latest: $latest)"
if [ "$dry" = 1 ]; then
  printf '%s\n' "$notes"
  exit 0
fi

printf '%s\n' "$notes" |
  gh release create "$tag" --target "$sha" --title "$name $version" \
    --notes-file - --latest="$latest"
