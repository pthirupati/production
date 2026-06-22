#!/usr/bin/env bash
# Email the FixitLab cluster credential bundle to the operator.
# Transport priority (no SendGrid required): Gmail API (GMAIL_OAUTH_*) →
# Gmail SMTP (EMAIL_HOST_USER/PASSWORD app password) → SendGrid (only if set).
# Sending creds come from the deployed node's env; the attachment stays redacted.
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
#               SECRETS_ROTATED   (1/0)   — did this run rotate infra secrets?
#               GH_SYNC_STATUS    (ok|failed|skipped) — were the rotated secrets
#                                  written back to GitHub Environment secrets?
#               VAULT_SYNC_STATUS (ok|failed|skipped) — were the Vault AppRole/
#                                  unseal secrets synced to GitHub?
# When secrets were rotated, the body STATES whether the GitHub/Vault sync
# succeeded so the operator knows if a MANUAL GitHub-secret update is needed.
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

# ── Build a redacted copy of the env ──
# Per policy, email ALL rotated infra passwords (Django/Postgres/Redis/RabbitMQ/
# admin/Vault/JWT/webhooks) but NEVER the DO API token, the SSH private key, or the
# GitHub / Google credentials (those stay in GitHub secrets only).
REDACTED_ENV="$(mktemp)"
trap 'rm -f "$REDACTED_ENV" "${BODY_FILE:-}" "${PAYLOAD_FILE:-}"' EXIT
REDACT_KEYS='DO_API_TOKEN|DO_SSH_KEY_PEM|PROD_SSH_KEY|GH_ADMIN_TOKEN|GITHUB_TOKEN|GITHUB_CLIENT_SECRET|GOOGLE_CLIENT_SECRET|GMAIL_OAUTH_CLIENT_SECRET|GMAIL_OAUTH_REFRESH_TOKEN'
grep -v -E "^(${REDACT_KEYS})=" "$ENV_FILE" > "$REDACTED_ENV" || true
{
  echo ""
  echo "# NOTE: DO_API_TOKEN, SSH private keys, and GitHub/Google secrets are"
  echo "# intentionally redacted here — they live in GitHub secrets only."
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

# ── Build the secret-sync status block ──
# Tells the operator, in plain language, where the rotated credentials persisted.
# These are now TWO INDEPENDENT signals:
#   VAULT_SYNC_STATUS — rotated env persisted to Vault secret/fixitlab/env? This is
#                       the REAL login-persistence path: every later deploy overlays
#                       it, so admin login survives WITHOUT touching GitHub secrets.
#   GH_SYNC_STATUS    — GitHub Environment secret (PRODUCTION_ENV_B64) write-back?
#                       OPTIONAL now (a 403 without a classic PAT is expected and is
#                       NOT login-critical once Vault persisted).
SECRETS_ROTATED="${SECRETS_ROTATED:-0}"
GH_SYNC_STATUS="${GH_SYNC_STATUS:-skipped}"
VAULT_SYNC_STATUS="${VAULT_SYNC_STATUS:-skipped}"

_vault_line() {  # $1=status
  case "$1" in
    ok|OK|1|true)    echo "  Vault (secret/fixitlab/env): PERSISTED — rotated secrets are the cross-deploy source of truth; admin login persists automatically. No action needed." ;;
    failed|FAILED|0) echo "  Vault (secret/fixitlab/env): FAILED — rotated secrets did NOT persist to Vault. Re-run the deploy or update the GitHub secret from the attached env (see below)." ;;
    *)               echo "  Vault (secret/fixitlab/env): not written this run." ;;
  esac
}
_gh_line() {  # $1=status
  case "$1" in
    ok|OK|1|true)    echo "  GitHub secret (PRODUCTION_ENV_B64): synced — kept in step with the rotation." ;;
    failed|FAILED|0) echo "  GitHub secret (PRODUCTION_ENV_B64): not written (HTTP 403 without a classic 'repo' PAT). OPTIONAL — not login-critical because Vault holds the rotated secrets. Set GH_ADMIN_TOKEN to a classic PAT to also keep this fresh." ;;
    *)               echo "  GitHub secret (PRODUCTION_ENV_B64): not applicable this run." ;;
  esac
}

SYNC_BLOCK="$(mktemp)"
{
  if _is_true "$SECRETS_ROTATED"; then
    echo "Secret rotation: YES — infra secrets were rotated this run."
    echo "Persistence status:"
    _vault_line "$VAULT_SYNC_STATUS"
    _gh_line "$GH_SYNC_STATUS"
    case "$VAULT_SYNC_STATUS" in
      ok|OK|1|true)
        echo "  RESULT: login WILL persist across deploys (Vault is authoritative); the"
        echo "  GitHub-secret write-back above is optional."
        ;;
      *)
        echo "  ACTION REQUIRED: rotated secrets did NOT persist to Vault. To avoid the"
        echo "  next deploy reverting to stale credentials, copy the values from the"
        echo "  attached env into the GitHub PRODUCTION_ENV_B64 secret, or re-run the deploy."
        ;;
    esac
  else
    echo "Secret rotation: NO — existing secrets were preserved (nothing to persist)."
  fi
} > "$SYNC_BLOCK"
SYNC_STATUS_TEXT="$(cat "$SYNC_BLOCK")"
rm -f "$SYNC_BLOCK"

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

${SYNC_STATUS_TEXT}

The full .env.production is attached (DO_API_TOKEN and SSH private keys redacted).
Store this email securely and delete after transferring to your password manager.
EOF

echo "=== FixitLab email credentials (dry_run=$DRY_RUN) ==="

# Safety guard (runs for BOTH dry-run and real send): none of the redacted keys
# may appear in the attachment.
if grep -qE "^(${REDACT_KEYS})=" "$REDACTED_ENV"; then
  echo "FATAL: a redacted secret (DO/SSH/GitHub/Google) leaked into the attachment" >&2
  exit 1
fi

# Send via the first available transport, preferring the platform's own Gmail
# (no SendGrid required): Gmail API (GMAIL_OAUTH_*) → Gmail SMTP
# (EMAIL_HOST_USER/PASSWORD app password) → SendGrid (only if SENDGRID_API_KEY set).
# Sending credentials are read from the FULL env ($ENV_FILE); the attachment stays
# redacted. Stdlib only — no extra runner packages.
SEND_RC=0
python3 - "$BODY_FILE" "$REDACTED_ENV" "$CRED_TO" "$CRED_FROM" "$ENV_FILE" "$DRY_RUN" <<'PY' || SEND_RC=$?
import base64, json, re, smtplib, ssl, sys, urllib.request, urllib.parse
from email.message import EmailMessage

body_path, att_path, to, frm, env_path, dry = sys.argv[1:7]
dry = dry in ("1", "true", "TRUE", "yes", "on")
body = open(body_path, encoding="utf-8").read()
att_bytes = open(att_path, "rb").read()
SUBJECT = "FixitLab cluster — deployment credentials"

env = {}
for line in open(env_path, encoding="utf-8", errors="replace"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

def g(*names):
    for n in names:
        if env.get(n):
            return env[n]
    return ""

gmail_cid = g("GMAIL_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID")
gmail_csec = g("GMAIL_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET")
gmail_rt = g("GMAIL_OAUTH_REFRESH_TOKEN")
smtp_user = g("EMAIL_HOST_USER")
smtp_pass = g("EMAIL_HOST_PASSWORD")
sendgrid = g("SENDGRID_API_KEY")
from_addr = frm or g("DEFAULT_FROM_EMAIL") or smtp_user or "no-reply@fixitlab.in"
m = re.search(r"<([^>]+)>", from_addr)
from_email = m.group(1) if m else from_addr

def mime():
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = SUBJECT, from_addr, to
    msg.set_content(body)
    msg.add_attachment(att_bytes, maintype="text", subtype="plain",
                       filename="env.production.redacted.txt")
    return msg

def via_gmail_api():
    data = urllib.parse.urlencode({
        "client_id": gmail_cid, "client_secret": gmail_csec,
        "refresh_token": gmail_rt, "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(
            urllib.request.Request("https://oauth2.googleapis.com/token", data=data),
            timeout=30) as r:
        tok = json.loads(r.read())["access_token"]
    raw = base64.urlsafe_b64encode(mime().as_bytes()).decode()
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw}).encode(),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    return "Gmail API"

def via_gmail_smtp():
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(smtp_user, smtp_pass)
        s.send_message(mime(), from_addr=from_email, to_addrs=[to])
    return "Gmail SMTP"

def via_sendgrid():
    payload = {"personalizations": [{"to": [{"email": to}]}],
               "from": {"email": from_email}, "subject": SUBJECT,
               "content": [{"type": "text/plain", "value": body}],
               "attachments": [{"content": base64.b64encode(att_bytes).decode(),
                                "type": "text/plain",
                                "filename": "env.production.redacted.txt",
                                "disposition": "attachment"}]}
    req = urllib.request.Request("https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + sendgrid, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    return "SendGrid"

transports = []
if gmail_cid and gmail_csec and gmail_rt: transports.append(("Gmail API", via_gmail_api))
if smtp_user and smtp_pass: transports.append(("Gmail SMTP", via_gmail_smtp))
if sendgrid: transports.append(("SendGrid", via_sendgrid))

if dry:
    print("DRY_RUN — available transports: " + (", ".join(t[0] for t in transports) or "NONE"))
    print("  To: %s   From: %s   Subject: %s" % (to, from_addr, SUBJECT))
    print("----- body preview -----\n" + body)
    print("----- attachment: env.production.redacted.txt (%d bytes) -----" % len(att_bytes))
    sys.exit(0 if transports else 3)

if not transports:
    sys.stderr.write("no email transport available (need GMAIL_OAUTH_*, EMAIL_HOST_USER/PASSWORD, or SENDGRID_API_KEY)\n")
    sys.exit(3)

last = ""
for name, fn in transports:
    try:
        print("Credentials email sent to %s via %s" % (to, fn()))
        sys.exit(0)
    except Exception as e:
        last = "%s failed: %s" % (name, e)
        sys.stderr.write(last + "\n")
sys.stderr.write("all transports failed: %s\n" % last)
sys.exit(4)
PY

if [ "$SEND_RC" -ne 0 ]; then
  if [ "$SEND_RC" -eq 3 ]; then
    fail_or_warn "no email transport configured (set Gmail OAuth or Gmail SMTP in PRODUCTION_ENV_B64, or SENDGRID_API_KEY)"
  else
    fail_or_warn "credentials email failed (rc=$SEND_RC)"
  fi
fi
echo "=== email credentials done ==="
