#!/bin/bash
# Grades the three phases the incident actually requires: DETECT (the cert is
# readable and its expiry is known), REPLACE (a fresh cert is installed and
# nginx accepts it), and PREVENT (an expiry monitor exists that would page
# before the next 03:00 outage instead of after it).
#
# WHY a prevent phase: replacing the cert alone puts the same 365-day fuse back
# in the wall. The recurrence is the actual defect, so it is graded.

CERT=/etc/nginx/ssl/cert.pem
KEY=/etc/nginx/ssl/key.pem

# --- DETECT -----------------------------------------------------------------
END_DATE=$(openssl x509 -in "$CERT" -noout -enddate 2>/dev/null | sed 's/notAfter=//')
if [ -z "$END_DATE" ]; then
  echo "FAIL: no readable certificate at $CERT"
  exit 1
fi

# --- REPLACE ----------------------------------------------------------------
# `openssl -checkend <seconds>` instead of parsing notAfter with `date -d`:
# -d is GNU-only, so on a BSD/macOS host the old parse fell through to
# `|| echo 0` and failed every learner with a perfectly valid certificate.
# -checkend is portable and answers exactly the question being asked.
if ! openssl x509 -in "$CERT" -noout -checkend $((86400 * 7)) >/dev/null 2>&1; then
  echo "FAIL: certificate expires $END_DATE (within 7 days) — regenerate with openssl (days >= 365) and reload nginx"
  exit 1
fi

# The key must actually match the cert. A learner who regenerates only the cert
# leaves nginx serving a handshake that dies at SSL_CTX_use_PrivateKey; checking
# notAfter alone would call that a pass.
CERT_MOD=$(openssl x509 -in "$CERT" -noout -modulus 2>/dev/null | openssl md5)
KEY_MOD=$(openssl rsa -in "$KEY" -noout -modulus 2>/dev/null | openssl md5)
if [ -z "$KEY_MOD" ] || [ "$CERT_MOD" != "$KEY_MOD" ]; then
  echo "FAIL: $KEY does not match $CERT — regenerate the key and cert together"
  exit 1
fi

if ! nginx -t 2>/dev/null; then
  echo "FAIL: nginx config invalid — run 'nginx -t', fix the errors, then reload"
  exit 1
fi

# --- PREVENT ----------------------------------------------------------------
# Accept any monitor the learner wires up (cron, systemd timer, or a script a
# scheduler calls) as long as it is executable and genuinely reports on expiry.
# We grade behaviour, not a filename: the script is run against a deliberately
# expired probe cert and must exit non-zero, then against the live healthy cert
# and must exit zero. A stub that always says OK fails the first half; a stub
# that always alarms fails the second.
MONITOR=""
for candidate in \
  /usr/local/bin/check-cert-expiry \
  /usr/local/bin/cert-expiry-check \
  /opt/fixitlab/check-cert-expiry.sh \
  /etc/cron.daily/cert-expiry; do
  if [ -x "$candidate" ]; then
    MONITOR="$candidate"
    break
  fi
done

if [ -z "$MONITOR" ]; then
  echo "FAIL: no certificate-expiry monitor installed — the cert is renewed but"
  echo "      nothing warns you before the next expiry. Install an executable"
  echo "      checker at /usr/local/bin/check-cert-expiry that takes a cert path,"
  echo "      exits non-zero when it expires within the warning window (30 days),"
  echo "      and schedule it (cron or systemd timer)."
  exit 1
fi

# The probe is a shipped, already-expired certificate (notAfter=2020-01-02)
# rather than one minted here: `openssl req -x509` cannot backdate validity
# portably — `-not_before/-not_after` is missing on LibreSSL and `-days -3`
# is silently accepted but wraps to a *future* date, which would hand the
# monitor a valid cert and make this assertion vacuous.
PROBE_EXPIRED="$(dirname "$0")/probe-expired.pem"
if [ ! -f "$PROBE_EXPIRED" ]; then
  echo "FAIL: grader asset probe-expired.pem missing next to check.sh"
  exit 1
fi

if "$MONITOR" "$PROBE_EXPIRED" >/dev/null 2>&1; then
  echo "FAIL: $MONITOR reported an expired/expiring certificate as healthy."
  echo "      It must exit non-zero when the cert is inside the warning window."
  exit 1
fi

if ! "$MONITOR" "$CERT" >/dev/null 2>&1; then
  echo "FAIL: $MONITOR reports the freshly renewed $CERT as failing."
  echo "      A monitor that always alarms is the same as no monitor."
  exit 1
fi

# The monitor must be scheduled, otherwise nobody ever runs it.
if ! { crontab -l 2>/dev/null; cat /etc/crontab /etc/cron.d/* 2>/dev/null; } | grep -qF "$(basename "$MONITOR")" \
   && [ ! -x "/etc/cron.daily/$(basename "$MONITOR")" ] \
   && ! ls /etc/systemd/system/*cert*.timer >/dev/null 2>&1; then
  echo "FAIL: $MONITOR exists but is not scheduled — add a cron entry"
  echo "      (crontab, /etc/cron.d, /etc/cron.daily) or a systemd timer."
  exit 1
fi

echo "OK: certificate renewed (expires $END_DATE), key matches, nginx config valid"
echo "OK: expiry monitor $MONITOR is installed, correct, and scheduled"
exit 0
