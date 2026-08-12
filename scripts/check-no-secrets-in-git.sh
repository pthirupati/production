#!/usr/bin/env bash
# Fail CI if tracked files contain production secrets (tokens, keys, passwords).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
SELF="scripts/check-no-secrets-in-git.sh"
# Duplicate copy kept under backend/ for some CI jobs — exclude both from self-hits.
SELF_BACKEND="backend/scripts/check-no-secrets-in-git.sh"

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
SECRET_ASSIGN_RE='(SECRET_KEY|_PASSWORD|_PASS|PASSWORD|_SECRET|API_TOKEN|ACCESS_KEY|PRIVATE_KEY|_TOKEN)[[:space:]]*[:=][[:space:]]*["'"'"']?[^[:space:]"'"'"']{16,}'
SIM_MARKER='SIMULATED-CREDENTIAL'

# `KEY_SECRET` was widened to `_SECRET` because it did NOT match `CLIENT_SECRET`,
# and two live 64-hex OAuth client secrets sat unredacted in a tracked file while
# this script reported "no secrets detected". A name-list that has to enumerate
# every vendor's spelling will always trail the code; the suffix matches them all.
#
# Credentials in URL userinfo (scheme://user:password@host) are a separate blind
# spot and need their own rule: the assignment rule matches KEY=value, so a broker
# URL hides the password *inside* the value. That is not hypothetical — the
# RabbitMQ password was redacted on two lines of SETUP_COMPLETE.md and then sat in
# clear text ten lines below, embedded in CELERY_BROKER_URL, making both
# redactions void. Require 8+ chars so `http://user:@host` and short scheme-ish
# strings do not trip it; placeholders are filtered by PLACEHOLDER_RE as usual.
URL_USERINFO_RE='[a-zA-Z][a-zA-Z0-9+.-]*://[^:/@[:space:]]+:[^@/[:space:]]{8,}@'


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
PLACEHOLDER_RE='change[-_ ]?me|your[-_ ]?(key|token|secret|password|pass|value|domain|email|account|id)|YOUR_|<[a-z_]+>|xxxx|placeholder|replace[-_ ]?me|example\.com|\$\{|\$\(|\{\{|\{[A-Za-z_][A-Za-z0-9_.]*\}|os\.environ|env\(|getenv|process\.env|secrets\.|vault_|REDACTED|token-here|app-password|generate[-_ ][a-z0-9]|paste[-_ ][a-z]|random[-_ ]?string|^[[:space:]]*#'

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

# Value-level allowlist, NOT path-level suppression.
#
# This used to exclude two whole paths (the AWS console-sim component tree and
# the vmware_sim aws_engine) because the sim prints Amazon's published
# documentation key. That blinded the entire high-confidence pass to a directory
# tree: a probe file containing a real-shaped ghp_ token written under
# frontend/src/components/aws/ was scanned and reported "no secrets detected",
# while the same probe fails the build now. Suppressing a *value* the whole
# industry already knows costs nothing; suppressing a *directory* hides every
# future leak inside it.
#
# Entries must stay exact literals — never regexes. An allowlist suppresses
# findings, so a PEM-header + ".*" style entry would mute every real PEM in the
# repo, which is precisely the failure PLACEHOLDER_RE's `/your/` scar records.
# Anything shorter than a complete credential can also occur inside a real one.
# If a fake value is too variable to write out in full, it needs a
# SIMULATED-CREDENTIAL marker at the source instead.
#
# AKIAIOSFODNN7EXAMPLE is AWS's own documentation key, reserved by Amazon and
# valid nowhere. It is the only allowlisted value in the tree today.
ALLOWED_SECRET_VALUES=(
  'AKIAIOSFODNN7EXAMPLE'
)

PREFIX_EXCLUDES=(
  ":!$SELF"
  ":!$SELF_BACKEND"
  # Scanner unit tests intentionally quote pattern shapes; they are not secrets.
  ':!backend/tests/test_secret_scanner_rules.py'
)

# Narrow, temporary carve-out — one file, one pattern, not a directory tree.
#
# The AWS console sim's `create-key-pair` prints a fake PEM whose body is prose
# ("ThisIsALabKeyPairAndContainsNoRealCryptographicMaterialAtAll"). The rule
# matches the PEM *header*, so there is no high-entropy literal to allowlist.
# The right fix is a SIMULATED-CREDENTIAL marker next to that value — pass 1 now
# honours markers — but awscli.js is owned by another change in flight.
#
# Unlike the old directory-wide pathspec, this suppresses only the PEM pattern in
# one named file: a dop_v1_/ghp_/AKIA leak in that same file, or any leak
# elsewhere under components/aws/, still fails the build.
SIM_PEM_FILE='frontend/src/components/aws/terminal/awscli.js'
PEM_RE='-----BEGIN (RSA )?PRIVATE KEY-----'

# Match on file:line so a line carrying only an allowlisted value can be dropped
# while every other line in the same file still reports. `-l` (filenames only)
# could not make that distinction, which is why the old version had to exclude
# whole paths.
ALLOWED_VALUES_RE="$(IFS='|'; printf '%s' "${ALLOWED_SECRET_VALUES[*]}")"

while IFS= read -r hit; do
  [ -z "$hit" ] && continue
  file="${hit%%:*}"
  rest="${hit#*:}"
  lineno="${rest%%:*}"
  line="${rest#*:}"

  # Strip the allowlisted literals, then re-test: a line that still matches has
  # a second, non-allowlisted secret on it and must not be waved through.
  stripped="$(printf '%s' "$line" | sed -E "s/${ALLOWED_VALUES_RE}//g")"
  if ! printf '%s' "$stripped" | grep -qE "$COMBINED_PREFIX_RE"; then
    continue
  fi

  # Same SIMULATED-CREDENTIAL escape hatch passes 2 and 3 already honour. Pass 1
  # needs it too now that it no longer suppresses whole directories: a fake value
  # whose body is prose cannot be an exact-literal allowlist entry. A marker is
  # auditable — it sits next to the fake value, where a reviewer sees it.
  from=$(( lineno > 8 ? lineno - 8 : 1 ))
  if sed -n "${from},${lineno}p" "$file" 2>/dev/null | grep -q "$SIM_MARKER"; then
    continue
  fi

  # The one-file/one-pattern carve-out described above. Both conditions must
  # hold, so this cannot grow into a directory-wide blind spot by accident.
  # `-e` is required: PEM_RE starts with dashes, which grep would read as flags.
  if [ "$file" = "$SIM_PEM_FILE" ] && printf '%s' "$stripped" | grep -qE -e "$PEM_RE"; then
    remainder="$(printf '%s' "$stripped" | sed -E "s/${PEM_RE}//g")"
    if ! printf '%s' "$remainder" | grep -qE "$COMBINED_PREFIX_RE"; then
      continue
    fi
  fi

  echo "  FAIL: $file:$lineno matches high-confidence secret pattern"
  FAIL=1
done < <(git grep -nIE "$COMBINED_PREFIX_RE" -- . "${PREFIX_EXCLUDES[@]}" 2>/dev/null)

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
  ":!$SELF_BACKEND"
  ':!*example*'
  ':!scenarios/**'
  ':!backend/apps/vmware_sim/**'
  ':!backend/apps/labs/provisioner/simulation/**'
  ':!**/management/commands/data/**'
  ':!**/curriculum/**'
  ':!**/tests/**'
  ':!**/test_*.py'
  ':!**/*.test.js'
  ':!**/*.test.jsx'
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

# Same filtering, separate rule: a password inside scheme://user:pass@host is not
# an assignment, so the loop above cannot see it.
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
  echo "  FAIL: $file:$lineno embeds a credential in a URL (scheme://user:****@host)"
  FAIL=1
done < <(git grep -nIE "$URL_USERINFO_RE" -- "${GENERIC_INCLUDES[@]}" "${GENERIC_EXCLUDES[@]}" 2>/dev/null)

if [ $FAIL -eq 0 ]; then
  echo "  OK: no secrets detected in tracked files"
  exit 0
fi

echo ""
echo "Never commit deploy/production.env or deploy/vault-*.json — use Vault or GitHub Environment secrets."
echo "See docs/GITHUB_SECRETS.md"
exit 1
