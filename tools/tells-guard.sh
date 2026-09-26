#!/usr/bin/env bash
# tells-guard — this repository is public and describes a real, running
# architecture WITHOUT pointing at it. Nothing here may identify the
# infrastructure it was written from: no IP addresses, no real domains, no
# provider names, no node names. Examples use example.com and the documentation
# address ranges.
#
# Three checks over every tracked file:
#   [1] IPv4 literals outside the documentation ranges (RFC 5737) and the
#       ranges that identify nothing (loopback, private, CGNAT, link-local)
#   [2] domain-looking strings outside an allowlist of upstream projects and
#       example.* names
#   [3] FORBIDDEN_STRINGS — a newline-separated list kept in a CI secret, never
#       in the repository: the real domains, provider and node names this
#       guard exists to keep out. A list of what must not leak cannot itself be
#       published, so it lives where only CI can read it.
#
# Exit 1 on any finding. Tracked files only — run it after `git add`.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
fail=0
files=$(git ls-files | grep -vE '^(LICENSE|tools/tells-guard\.sh)$' || true)
[ -n "$files" ] || { echo "no tracked files"; exit 0; }

echo "[1] IPv4 literals outside documentation and non-identifying ranges"
# Only 4-part values whose every part is <= 255 count, then the allowed ranges
# are removed. Note: a private or CGNAT address is allowed as a SHAPE (a mesh
# range in an example), not because ours would be harmless — a real one in
# those ranges still belongs in FORBIDDEN_STRINGS.
ipv4=$(echo "$files" | xargs grep -nHoE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' 2>/dev/null \
  | awk -F: '{ split($NF, o, "."); ok = 1; for (i = 1; i <= 4; i++) if (o[i] > 255) ok = 0; if (ok) print }' \
  | grep -vE ':(192\.0\.2|198\.51\.100|203\.0\.113)\.[0-9]+$' \
  | grep -vE ':(127|10)\.[0-9]+\.[0-9]+\.[0-9]+$' \
  | grep -vE ':192\.168\.[0-9]+\.[0-9]+$' \
  | grep -vE ':172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+$' \
  | grep -vE ':100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]+\.[0-9]+$' \
  | grep -vE ':169\.254\.[0-9]+\.[0-9]+$' \
  | grep -vE ':0\.0\.0\.0$' || true)
if [ -n "$ipv4" ]; then
  echo "$ipv4" | sed 's/^/  ::error::/'
  fail=1
else
  echo "  ok"
fi

echo "[2] domains outside the allowlist"
# Only strings ending in a real TLD count; dotted identifiers (file.md,
# obj.field) are not domains. md/sh/py/go/ts/js/rs are excluded on purpose:
# they are file extensions here, not TLDs.
TLDS='com|org|net|io|dev|cloud|site|ru|de|info|app|co|me|tech|xyz|cc|kz|pl|ua|by|su|eu|uk|nl|se|fi|tr|am|ge|uz|google|online|pro|top|space|store|shop|club|live|link|website|fun|click|pw|ws|sbs|cfd|software|rw'
ALLOW='(^|\.)(readme\.ru|example\.(com|org|net)|github\.com|githubusercontent\.com|github\.io|docs\.rw|remna\.st|t\.me|xtls\.github\.io|angie\.software|nginx\.org|nginx\.com|anthropic\.com|claude\.com|openai\.com|agentskills\.io|opensource\.org|letsencrypt\.org|gstatic\.com|cloudflare\.com|golang\.org|go\.dev|docker\.com|docker\.io|ghcr\.io|debian\.org|ubuntu\.com|netbird\.io|semaphoreui\.com|openbao\.org|ansible\.com|context7\.com)$'
domains=$(echo "$files" | xargs grep -nHoE "\b[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.($TLDS)\b" 2>/dev/null \
  | ALLOW="$ALLOW" awk -F: '{ d = tolower($NF); if (d !~ ENVIRON["ALLOW"]) print }' || true)
if [ -n "$domains" ]; then
  echo "$domains" | sed 's/^/  ::error::/'
  fail=1
else
  echo "  ok"
fi

echo "[3] FORBIDDEN_STRINGS (from the CI secret)"
if [ -z "${FORBIDDEN_STRINGS:-}" ]; then
  # Not silently green: say that the strongest check did not run.
  echo "  ::warning::FORBIDDEN_STRINGS is empty — this check did not run"
  if [ "${REQUIRE_FORBIDDEN_STRINGS:-0}" = "1" ]; then
    echo "  ::error::REQUIRE_FORBIDDEN_STRINGS=1 but the secret is not set"
    fail=1
  fi
else
  hits=0
  while IFS= read -r needle; do
    needle=$(printf '%s' "$needle" | tr -d '\r')
    [ -n "$needle" ] || continue
    # Report the file and line, never the string itself: the log is public too.
    found=$(echo "$files" | xargs grep -nHiF -- "$needle" 2>/dev/null | cut -d: -f1,2 || true)
    if [ -n "$found" ]; then
      echo "$found" | sed 's/^/  ::error::forbidden string at /'
      hits=1
    fi
  done <<< "$FORBIDDEN_STRINGS"
  if [ "$hits" = 1 ]; then fail=1; else echo "  ok"; fi
fi

if [ "$fail" = 1 ]; then
  echo "FAILED: something here would identify the infrastructure."
  exit 1
fi
echo "OK: nothing identifying found."
