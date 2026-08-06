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

# Placeholders and indirection that are legitimately committed: ${VAR}, $(cmd),
# {{ tpl }}, os.environ[...], env(...), getenv(...), <YOUR_KEY>, change-me, …
#
# NOTE: keep these anchored to placeholder *phrases*. A bare /your/ was tried and
# it silently suppressed a real AWS_SECRET_ACCESS_KEY leak whose value happened to
# contain that substring — a false negative is far worse here than a false
# positive, so require the placeholder word to look deliberate.
# `\{[A-Za-z_][A-Za-z0-9_.\[\]]*\}` covers Python f-string / .format() fields, e.g.
# print(f"GMAIL_OAUTH_REFRESH_TOKEN={creds.refresh_token}") in the OAuth helper
# script — that line *emits* a secret at runtime, it does not contain one. The
# earlier `\$\{` only caught shell-style ${VAR}.
PLACEHOLDER_RE='change[-_ ]?me|your[-_ ]?(key|token|secret|password|pass|value|domain|email|account|id)|YOUR_|<[a-z_]+>|xxxx|placeholder|replace[-_ ]?me|example\.com|\$\{|\$\(|\{\{|\{[A-Za-z_][A-Za-z0-9_.]*\}|os\.environ|env\(|getenv|process\.env|secrets\.|vault_|REDACTED|token-here|app-password|^[[:space:]]*#'

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

# ── Pass 1: high-confidence prefix patterns, one `git grep` for all of them ───
#
# PERFORMANCE: this used to be a per-file bash loop that spawned `grep` once per
# file per pattern — 16,372 tracked files x 8 patterns is ~131,000 process
# spawns, and the whole script took 8m10s (228s of that pure system time). As a
# PR gate that is long enough that someone eventually deletes the step, which
# would be worse than having no scanner. `git grep` does the whole tree in one
# process with its own pathspec exclusions, so keep it that way: do NOT
# reintroduce a per-file loop here.
COMBINED_PREFIX_RE="$(IFS='|'; printf '%s' "${PATTERNS[*]}")"

# Documentation-style example AWS keys live in the AWS console sim and engine.
PREFIX_EXCLUDES=(
  ":!$SELF"
  ':!frontend/src/components/aws/**'
  ':!backend/apps/vmware_sim/aws_engine.py'
)

while IFS= read -r hit; do
  [ -z "$hit" ] && continue
  echo "  FAIL: $hit matches high-confidence secret pattern"
  FAIL=1
done < <(git grep -lIE "$COMBINED_PREFIX_RE" -- . "${PREFIX_EXCLUDES[@]}" 2>/dev/null)

# ── Pass 2: generic NAME=value entropy, again a single `git grep` ──────────────
#
# Path exclusions are expressed as git pathspecs so they are applied by git
# rather than by re-testing every path in bash. They mirror the `case` list in
# check_generic_secrets(), which still guards the per-match path for anything
# that slips through.
GENERIC_INCLUDES=(
  '*.md' '*.txt' '*.env' '*.sh' '*.yml' '*.yaml' '*.json'
  '*.py' '*.js' '*.jsx' '*.conf' '*.ini' '*.cfg' '*.toml'
)
GENERIC_EXCLUDES=(
  ":!$SELF"
  ':!*example*'
  ':!scenarios/**'
  ':!backend/apps/vmware_sim/**'
  ':!backend/apps/labs/provisioner/simulation/**'
  ':!**/management/commands/data/**'
  ':!**/curriculum/**'
  ':!**/tests/**'
  ':!**/test_*.py'
  # `test/` singular is a real top-level dir here (smoketest_e2e.py), and its
  # filename does not match test_*.py — both misses were caught by a live run.
  ':!test/**'
  ':!**/*smoketest*'
  ':!.github/workflows/**'
)

# `git grep -n` gives file:line:content in one shot. Only matched lines reach
# the (cheap) per-line placeholder + marker checks.
while IFS= read -r hit; do
  [ -z "$hit" ] && continue
  file="${hit%%:*}"
  rest="${hit#*:}"
  lineno="${rest%%:*}"
  line="${rest#*:}"

  if printf '%s' "$line" | grep -qiE "$PLACEHOLDER_RE"; then
    continue
  fi
  from=$(( lineno > 8 ? lineno - 8 : 1 ))
  if sed -n "${from},${lineno}p" "$file" 2>/dev/null | grep -q "$SIM_MARKER"; then
    continue
  fi
  echo "  FAIL: $file:$lineno assigns a high-entropy secret in plain text"
  FAIL=1
done < <(git grep -nIE "$SECRET_ASSIGN_RE" -- "${GENERIC_INCLUDES[@]}" "${GENERIC_EXCLUDES[@]}" 2>/dev/null)

if [ $FAIL -eq 0 ]; then
  echo "  OK: no secrets detected in tracked files"
  exit 0
fi

echo ""
echo "Never commit deploy/production.env or deploy/vault-*.json — use Vault or GitHub Environment secrets."
echo "See docs/GITHUB_SECRETS.md"
exit 1
