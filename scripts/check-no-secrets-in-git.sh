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

# ── Generic high-entropy assignments ──────────────────────────────────────────
# The prefix patterns below only catch secrets whose FORMAT is recognisable
# (dop_v1_, ghp_, AKIA…). They completely missed SETUP_COMPLETE.md, which was
# tracked with a Django SECRET_KEY plus Postgres/Redis/RabbitMQ/Razorpay
# passwords in plain `NAME=value` form. This pass covers that shape.
#
# IMPORTANT — false positives are the real failure mode here. The repo contains
# 14 *simulated* console logins (lab_ide/lab_ide@123 and friends) that exist to
# make fake consoles feel real: they are printed on screen with an autofill
# button and protect nothing. Matching them would mute this scanner. Each is
# annotated with a SIMULATED-CREDENTIAL marker, and we skip any match whose
# preceding lines carry that marker. Never remove the marker to "fix" a hit —
# if a genuine secret ever appears near one, move the secret out instead.
# The value class must be permissive: real secrets contain punctuation
# (Django SECRET_KEYs routinely include !#$%^&*()=+), and an earlier, narrower
# class of [A-Za-z0-9+/_@%.-] silently matched only 4 of the 10 known-leaked
# lines in SETUP_COMPLETE.md because the 16-char run broke at the first special
# character. Match any 16+ run of non-space, non-quote instead.
SECRET_ASSIGN_RE='(SECRET_KEY|_PASSWORD|_PASS|PASSWORD|KEY_SECRET|API_TOKEN|ACCESS_KEY|PRIVATE_KEY|_TOKEN)[[:space:]]*[:=][[:space:]]*["'"'"']?[^[:space:]"'"'"']{16,}'
SIM_MARKER='SIMULATED-CREDENTIAL'

check_generic_secrets() {
  local file="$1" line lineno
  # Paths that are definitionally non-secret. Every exclusion here was verified
  # against a real hit during the 2026-08-06 audit — see the triage table in
  # docs/AUDIT_2026_08_TODO.md §S2. Keeping these out is what makes the signal
  # trustworthy; a scanner that cries wolf gets switched off.
  case "$file" in
    # Env EXAMPLES and docs placeholders are legitimately committed.
    *.example|*example*|env.production.example) return 0 ;;
    # scenarios/ is LAB CONTENT. Its YAML deliberately contains fake credentials
    # (a lab that teaches you to rotate a DB password has to name one).
    scenarios/*) return 0 ;;
    # Simulation engines seed fake console state for the same reason.
    backend/apps/vmware_sim/*|backend/apps/labs/provisioner/simulation/*) return 0 ;;
    # Tutorial/curriculum content — teaching material. Real hit: a Kubernetes
    # Secret manifest inside tutorials_extra.json, which is the lesson itself.
    */management/commands/data/*|*/curriculum/*) return 0 ;;
    # Test fixtures. Real hit: RAZORPAY_KEY_SECRET in test_billing_webhooks.py.
    */tests/*|*/test_*.py|*_test.py|*.test.js|*.test.jsx) return 0 ;;
    # CI workflow env holds throwaway SECRET_KEYs for the ephemeral test DB;
    # genuine CI secrets come from GitHub Environments, never literals. The
    # FORBIDDEN_TRACKED + prefix passes above still cover these files.
    .github/workflows/*) return 0 ;;
  esac
  while IFS=: read -r lineno line; do
    [ -z "$lineno" ] && continue
    # Placeholders and indirection are fine: ${VAR}, $(cmd), {{ tpl }},
    # os.environ[...], env(...), getenv(...), <YOUR_KEY>, change-me, …
    # NOTE: keep these anchored to placeholder *phrases*. A bare /your/ was tried
    # and it silently suppressed a real AWS_SECRET_ACCESS_KEY leak whose value
    # happened to contain the substring — a false negative is far worse here than
    # a false positive, so require the placeholder word to look deliberate.
    if printf '%s' "$line" | grep -qiE 'change[-_ ]?me|your[-_ ]?(key|token|secret|password|pass|value|domain|email|account|id)|YOUR_|<[a-z_]+>|xxxx|placeholder|replace[-_ ]?me|example\.com|\$\{|\$\(|\{\{|os\.environ|env\(|getenv|process\.env|secrets\.|vault_|REDACTED|token-here|app-password|^[[:space:]]*#'; then
      continue
    fi
    # Skip if a SIMULATED-CREDENTIAL marker sits just above (the annotation is a
    # 5-line comment block, so look back a little further than that).
    local from=$(( lineno > 8 ? lineno - 8 : 1 ))
    if sed -n "${from},${lineno}p" "$file" 2>/dev/null | grep -q "$SIM_MARKER"; then
      continue
    fi
    echo "  FAIL: $file:$lineno assigns a high-entropy secret in plain text"
    FAIL=1
  done < <(grep -nE "$SECRET_ASSIGN_RE" "$file" 2>/dev/null)
}

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
  # AWS console / engine seed data uses documentation-style example access key
  # IDs (not real secrets). Same exclusion as frontend/src/components/aws/*.
  [[ "$f" == frontend/src/components/aws/* ]] && continue
  [[ "$f" == backend/apps/vmware_sim/aws_engine.py ]] && continue
  for pat in "${PATTERNS[@]}"; do
    if grep -qE "$pat" "$f" 2>/dev/null; then
      echo "  FAIL: $f matches high-confidence secret pattern"
      FAIL=1
      break
    fi
  done
  # Text-ish files also get the generic NAME=value entropy pass.
  case "$f" in
    *.md|*.txt|*.env|*.sh|*.yml|*.yaml|*.json|*.py|*.js|*.jsx|*.conf|*.ini|*.cfg|*.toml)
      check_generic_secrets "$f" ;;
  esac
done < <(git ls-files -z)

if [ $FAIL -eq 0 ]; then
  echo "  OK: no secrets detected in tracked files"
  exit 0
fi

echo ""
echo "Never commit deploy/production.env or deploy/vault-*.json — use Vault or GitHub Environment secrets."
echo "See docs/GITHUB_SECRETS.md"
exit 1
