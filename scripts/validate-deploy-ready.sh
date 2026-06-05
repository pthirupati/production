#!/usr/bin/env bash
# Pre-push validation — run locally before git push
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0

echo "=== FixitLab deploy readiness ==="

check() { [ "$1" -eq 0 ] && echo "  OK: $2" || { echo "  FAIL: $2"; FAIL=1; }; }

[ -f env.production.example ] && check 0 "env.production.example exists" || check 1 "env.production.example exists"
[ -f scripts/sync-production-env.sh ] && check 0 "sync-production-env.sh" || check 1 "sync-production-env.sh"
[ -f scripts/upload-secrets-to-github.sh ] && check 0 "upload-secrets-to-github.sh" || check 1 "upload-secrets-to-github.sh"
[ -f scripts/startup.sh ] && check 0 "scripts/startup.sh" || check 1 "scripts/startup.sh"
[ -f scripts/platform-start.sh ] && check 0 "scripts/platform-start.sh" || check 1 "scripts/platform-start.sh"
[ -f docker-compose.prod.yml ] && check 0 "docker-compose.prod.yml" || check 1 "docker-compose.prod.yml"
[ -f .github/workflows/platform-start.yml ] && check 0 "platform-start workflow" || check 1 "platform-start workflow"
[ -f .github/workflows/ci-cd-digitalocean.yml ] && check 0 "ci-cd workflow" || check 1 "ci-cd workflow"
[ -f docs/GITHUB_SECRETS.md ] && check 0 "GITHUB_SECRETS.md" || check 1 "GITHUB_SECRETS.md"

if git ls-files --error-unmatch deploy/production.env >/dev/null 2>&1; then
  echo "  WARN: deploy/production.env is tracked in git — run: git rm --cached deploy/production.env"
  FAIL=1
else
  check 0 "deploy/production.env not in git"
fi

ENV_CHECK="${ROOT}/deploy/production.env"
if [ -f "$ENV_CHECK" ]; then
  for key in DJANGO_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD SITE_URL JIRA_BASE_URL JIRA_API_TOKEN JIRA_PROJECT_KEY; do
    grep -q "^${key}=" "$ENV_CHECK" && [ -n "$(grep "^${key}=" "$ENV_CHECK" | cut -d= -f2- | tr -d '[:space:]')" ] && check 0 "$key set (local)" || check 1 "$key set (local)"
  done
  grep -q '^JIRA_ENABLED=true' "$ENV_CHECK" && check 0 "Jira enabled (local)" || echo "  INFO: Jira disabled in local env"
else
  echo "  INFO: deploy/production.env not found locally — create from env.production.example"
fi

grep -q '^LAB_PROVIDER=docker' env.production.example && check 0 "Docker labs in example" || check 1 "Docker labs in example"

MISSING=0
for f in $(find scenarios -name scenario.yaml); do
  d=$(dirname "$f")
  [ -f "$d/Dockerfile" ] || { echo "  FAIL: no Dockerfile in $d"; MISSING=1; }
  python3 -c "import yaml; yaml.safe_load(open('$f'))" 2>/dev/null || { echo "  FAIL: invalid YAML in $f"; MISSING=1; }
done
[ $MISSING -eq 0 ] && check 0 "all scenarios have Dockerfile + valid YAML" || FAIL=1

echo ""
if [ $FAIL -eq 0 ]; then
  echo "Ready to push. Then run: ./scripts/upload-secrets-to-github.sh"
  exit 0
fi
echo "Fix failures above before deploying."
exit 1
