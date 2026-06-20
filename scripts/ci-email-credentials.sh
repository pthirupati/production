#!/usr/bin/env bash
# Email the FixitLab cluster credential bundle to the operator via SendGrid.
#
# Body includes:
#   - D1 Edge public IP, D2/D3/D4 private IPs, site URL
#   - admin email + admin password
#   - Postgres / Redis / RabbitMQ / Vault credentials
#   - list of GitHub secrets that were updated by this run
# Attachment:
#   - the full .env.production, with the DO_API_TOKEN line REMOVED/REDACTED.
#
# Hard rule: DO_API_TOKEN is NEVER placed in the body or the attachment.
#
# Uses the SENDGRID_API_KEY GitHub secret. Does NOT fail the deploy if email
# fails — unless CREDENTIALS_EMAIL_REQUIRED=1.
#
# DRY_RUN=1 prints the curl command (API key masked) and a redacted preview of
# the payload WITHOUT sending. The DO token is stripped before any preview.
#
# Required env: CRED_TO (recipient), ENV_FILE (path to .env.production)
# Optional    : SENDGRID_API_KEY, CRED_FROM (default no-reply@fixitlab.in),
#               EDGE_PUBLIC_IP APP_PRIVATE_IP DATA_PRIVATE_IP LABS_PRIVATE_IP,
#               UPDATED_SECRETS (comma list), CREDENTIALS_EMAIL_REQUIRED
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
CRED_TO="${CRED_TO:?CRED_TO (recipient email) required}"
CRED_FROM="${CRED_FROM:-no-reply@fixitlab.in}"
ENV_FILE="${ENV_FILE:-.env.production}"
EMAIL_REQUIRED="${CREDENTIALS_EMAIL_REQUIRED:-0}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

[ -n "${SENDGRID_API_KEY:-}" ] && [ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::${SENDGRID_API_KEY}"

fail_or_warn() {
  local msg="$1"
  if _is_true "$EMAIL_REQUIRED"; then
    echo "ERROR: $msg (credentials_email_required=1)"; exit 1
  fi
  echo "WARN: $msg — continuing (credentials email is best-effort)"; exit 0
}

if [ ! -f "$ENV_FILE" ]; then
  fail_or_warn "env file not found: $ENV_FILE"
fi

# ── Build a redacted copy of the env (strip DO_API_TOKEN entirely) ──
REDACTED_ENV="$(mktemp)"
trap 'rm -f "$REDACTED_ENV" "${BODY_FILE:-}" "${PAYLOAD_FILE:-}"' EXIT
# Remove the DO token line and any DO_SSH_KEY_PEM material; replace with a notice.
grep -v -E '^(DO_API_TOKEN|DO_SSH_KEY_PEM|PROD_SSH_KEY)=' "$ENV_FILE" > "$REDACTED_ENV" || true
{
  echo ""
  echo "# NOTE: DO_API_TOKEN and SSH private keys are intentionally redacted from this file."
} >> "$REDACTED_ENV"

# Tolerant: a missing key returns empty (grep's non-zero must not abort the script).
env_val() { { grep "^$1=" "$ENV_FILE" 2>/dev/null || true; } | head -n1 | cut -d= -f2- | tr -d '\r'; }

ADMIN_EMAIL="$(env_val SUPERUSER_EMAIL)"
ADMIN_PASS="$(env_val SUPERUSER_PASSWORD)"
SITE_URL="$(env_val SITE_URL)"
PG_USER="$(env_val POSTGRES_USER)"
PG_PASS="$(env_val POSTGRES_PASSWORD)"
PG_DB="$(env_val POSTGRES_DB)"
REDIS_PASS="$(env_val REDIS_PASSWORD)"
RABBIT_USER="$(env_val RABBITMQ_USER)"
RABBIT_PASS="$(env_val RABBITMQ_PASS)"
VAULT_ADDR_V="$(env_val VAULT_ADDR)"

# ── Compose the plaintext body ──
BODY_FILE="$(mktemp)"
cat > "$BODY_FILE" <<EOF
FixitLab four-droplet cluster — deployment credentials

Site:            ${SITE_URL:-https://fixitlab.in}

Droplets
  D1 Edge  (public) : ${EDGE_PUBLIC_IP:-<edge-public-ip>}
  D2 App   (private): ${APP_PRIVATE_IP:-<app-private-ip>}
  D3 Data  (private): ${DATA_PRIVATE_IP:-<data-private-ip>}
  D4 Labs  (private): ${LABS_PRIVATE_IP:-<labs-private-ip>}

Admin login
  Email    : ${ADMIN_EMAIL:-<not set>}
  Password : ${ADMIN_PASS:-<not set>}

Datastores
  Postgres : user=${PG_USER:-fixitlab} db=${PG_DB:-fixitlab} password=${PG_PASS:-<not set>}  (host D3:6432 via pgBouncer)
  Redis    : password=${REDIS_PASS:-<not set>}  (host D1:6379)
  RabbitMQ : user=${RABBIT_USER:-fixitlab} password=${RABBIT_PASS:-<not set>}  (host D1:5672)
  Vault    : ${VAULT_ADDR_V:-http://<edge-private-ip>:8200}

GitHub secrets updated this run:
  ${UPDATED_SECRETS:-<none reported>}

The full .env.production is attached (DO_API_TOKEN and SSH private keys redacted).
Store this email securely and delete after transferring to your password manager.
EOF

# ── Build SendGrid v3 JSON payload (base64 attachment) ──
build_payload() {
  python3 - "$BODY_FILE" "$REDACTED_ENV" "$CRED_TO" "$CRED_FROM" <<'PY'
import base64, json, sys
body_path, att_path, to, frm = sys.argv[1:5]
body = open(body_path, encoding="utf-8").read()
att = base64.b64encode(open(att_path, "rb").read()).decode("ascii")
payload = {
    "personalizations": [{"to": [{"email": to}]}],
    "from": {"email": frm},
    "subject": "FixitLab cluster — deployment credentials",
    "content": [{"type": "text/plain", "value": body}],
    "attachments": [{
        "content": att,
        "type": "text/plain",
        "filename": "env.production.redacted.txt",
        "disposition": "attachment",
    }],
}
print(json.dumps(payload))
PY
}

echo "=== FixitLab email credentials (dry_run=$DRY_RUN) ==="

if _is_true "$DRY_RUN"; then
  echo "DRY_RUN — would POST to SendGrid (Authorization: Bearer ****) :"
  echo "  curl -s -X POST https://api.sendgrid.com/v3/mail/send -H 'Authorization: Bearer ****' -H 'Content-Type: application/json' --data @payload.json"
  echo "----- redacted body preview -----"
  cat "$BODY_FILE"
  echo "----- attachment: env.production.redacted.txt (DO_API_TOKEN stripped) -----"
  echo "  $(wc -l < "$REDACTED_ENV") lines; first line: $(head -n1 "$REDACTED_ENV")"
  # Safety assertion: the token ASSIGNMENT must not be present (the redaction
  # NOTE comment mentions the name DO_API_TOKEN, which is fine).
  if grep -qE '^DO_API_TOKEN=' "$REDACTED_ENV"; then echo "FATAL: token leaked into attachment"; exit 1; fi
  echo "=== email (dry-run) done — nothing sent ==="
  exit 0
fi

if [ -z "${SENDGRID_API_KEY:-}" ]; then
  fail_or_warn "SENDGRID_API_KEY not set"
fi

# Final safety assertion before sending.
if grep -q '^DO_API_TOKEN=' "$REDACTED_ENV"; then
  echo "FATAL: DO_API_TOKEN present in attachment — refusing to send"; exit 1
fi

PAYLOAD_FILE="$(mktemp)"
build_payload > "$PAYLOAD_FILE"

HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  https://api.sendgrid.com/v3/mail/send \
  -H "Authorization: Bearer ${SENDGRID_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @"$PAYLOAD_FILE" || echo "000")"

if [ "$HTTP_CODE" = "202" ]; then
  echo "Credentials email sent to ${CRED_TO} (HTTP 202)"
else
  fail_or_warn "SendGrid returned HTTP ${HTTP_CODE}"
fi

echo "=== email credentials done ==="
