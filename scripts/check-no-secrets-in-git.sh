#!/usr/bin/env bash
# Fail CI if tracked files contain production secrets (tokens, keys, passwords).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
SELF="scripts/check-no-secrets-in-git.sh"

echo "=== Checking tracked files for leaked secrets ==="

FORBIDDEN_TRACKED=(
  deploy/production.env
  deploy/vault-init.json
  deploy/vault-approle.env
  .env.production
  .env
)

for f in "${FORBIDDEN_TRACKED[@]}"; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo "  FAIL: $f is tracked in git — remove with: git rm --cached $f"
    FAIL=1
  fi
done

# Build patterns from parts so this script's source does not match its own rules.
DOP_PREFIX='dop_v1_'
PATTERNS=(
  "${DOP_PREFIX}[a-f0-9]{64}"
  "DO_API_TOKEN=${DOP_PREFIX}"
  '-----BEGIN (RSA )?PRIVATE KEY-----'
  'ghp_[a-zA-Z0-9]{20,}'
  'github_pat_[a-zA-Z0-9_]{20,}'
  'sk_live_[a-zA-Z0-9]{10,}'
  'rzp_live_[a-zA-Z0-9]{10,}'
  'AKIA[0-9A-Z]{16}'
)

while IFS= read -r -d '' f; do
  [[ "$f" == "$SELF" ]] && continue
  # AWS console simulation uses documentation-style example access key IDs (not real secrets).
  [[ "$f" == frontend/src/components/aws/* ]] && continue
  for pat in "${PATTERNS[@]}"; do
    if grep -qE "$pat" "$f" 2>/dev/null; then
      echo "  FAIL: $f matches high-confidence secret pattern"
      FAIL=1
      break
    fi
  done
done < <(git ls-files -z)

if [ $FAIL -eq 0 ]; then
  echo "  OK: no secrets detected in tracked files"
  exit 0
fi

echo ""
echo "Never commit deploy/production.env or deploy/vault-*.json — use Vault or GitHub Environment secrets."
echo "See docs/GITHUB_SECRETS.md"
exit 1
