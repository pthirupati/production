#!/usr/bin/env bash
# Pre-push validation — run locally before git push
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0

echo "=== FixitLab deploy readiness ==="

check() { [ "$1" -eq 0 ] && echo "  OK: $2" || { echo "  FAIL: $2"; FAIL=1; }; }

[ -f deploy/production.env ] && check 0 "deploy/production.env exists" || check 1 "deploy/production.env exists"
[ -f scripts/startup.sh ] && check 0 "scripts/startup.sh" || check 1 "scripts/startup.sh"
[ -f scripts/platform-start.sh ] && check 0 "scripts/platform-start.sh" || check 1 "scripts/platform-start.sh"
[ -f docker-compose.prod.yml ] && check 0 "docker-compose.prod.yml" || check 1 "docker-compose.prod.yml"
[ -f .github/workflows/platform-start.yml ] && check 0 "platform-start workflow" || check 1 "platform-start workflow"
[ -f .github/workflows/ci-cd-digitalocean.yml ] && check 0 "ci-cd workflow" || check 1 "ci-cd workflow"

for key in DJANGO_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD JIRA_BASE_URL JIRA_API_TOKEN SITE_URL; do
  grep -q "^${key}=" deploy/production.env && [ -n "$(grep "^${key}=" deploy/production.env | cut -d= -f2-)" ] && check 0 "$key set" || check 1 "$key set"
done

grep -q '^JIRA_ENABLED=true' deploy/production.env && check 0 "Jira enabled" || check 1 "Jira enabled"
grep -q '^LAB_PROVIDER=docker' deploy/production.env && check 0 "Docker labs" || check 1 "Docker labs"

MISSING=0
for f in $(find scenarios -name scenario.yaml); do
  d=$(dirname "$f")
  [ -f "$d/Dockerfile" ] || { echo "  FAIL: no Dockerfile in $d"; MISSING=1; }
done
[ $MISSING -eq 0 ] && check 0 "all scenarios have Dockerfile" || FAIL=1

echo ""
if [ $FAIL -eq 0 ]; then
  echo "Ready to push and run GitHub workflow."
  exit 0
fi
echo "Fix failures above before deploying."
exit 1
