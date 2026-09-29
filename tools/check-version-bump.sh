#!/usr/bin/env bash
# A change to what the plugin ships must come with a new version.
#
# Installed copies of the plugin are pinned to the `version` in
# .claude-plugin/plugin.json: Claude Code fetches a new copy only when that
# string changes. A merged change to skills/, agents/ or bin/ without a new
# version therefore never reaches anyone — and nothing says so. This fails
# instead:
#   [1] skills/, agents/ or bin/ changed but the version did not;
#   [2] the version went down or sideways instead of up;
#   [3] CHANGELOG.md has no "## <new version>" section.
# Changes elsewhere (READMEs, tests, tools, CI) need no release.
#
# Usage: check-version-bump.sh <base ref>   e.g. origin/main in a pull request
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
base=${1:?usage: check-version-bump.sh <base ref>}

# python3 on Linux; on Windows `python3` may be the Store stub that only prints
# an install hint, so take the first one that actually runs.
if python3 -c 'pass' 2>/dev/null; then py=python3; else py=python; fi

version_at() { # <ref> -> the plugin version at that ref
  git show "$1:.claude-plugin/plugin.json" |
    "$py" -c 'import json, sys; print(json.load(sys.stdin)["version"])'
}

shipped=$(git diff --name-only "$base"...HEAD | grep -E '^(skills|agents|bin)/' || true)
old=$(version_at "$base")
new=$(version_at HEAD)

if [ -z "$shipped" ]; then
  echo "OK: nothing the plugin ships changed; version stays $new."
  exit 0
fi

echo "Shipped files changed:"
echo "$shipped" | sed 's/^/  /'

if [ "$old" = "$new" ]; then
  echo "::error::[1] the plugin's shipped files changed but .claude-plugin/plugin.json is still $old — installed copies would never update. Bump the version and add a CHANGELOG.md section."
  exit 1
fi

if ! "$py" - "$old" "$new" <<'PY'
import sys
def key(v):
    return tuple(int(p) for p in v.split("."))
sys.exit(0 if key(sys.argv[2]) > key(sys.argv[1]) else 1)
PY
then
  echo "::error::[2] version $new is not greater than $old."
  exit 1
fi

if ! grep -qE "^## ${new//./\\.}( |$)" CHANGELOG.md; then
  echo "::error::[3] CHANGELOG.md has no '## $new' section describing this release."
  exit 1
fi

echo "OK: version $old -> $new, with a CHANGELOG.md section."
