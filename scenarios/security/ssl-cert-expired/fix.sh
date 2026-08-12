#!/bin/bash
set -e

# --- REPLACE: fresh cert + matching key, then reload nginx ------------------
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -newkey rsa:2048 -keyout /etc/nginx/ssl/key.pem -out /etc/nginx/ssl/cert.pem -days 365 -subj '/CN=localhost' >/dev/null 2>&1
nginx -t >/dev/null 2>&1 && (service nginx reload 2>/dev/null || systemctl reload nginx 2>/dev/null || true)

# --- PREVENT: expiry monitor so the renewal is scheduled, not paged ---------
# Exits non-zero while the cert is inside the 30-day warning window, which is
# what turns "expired at 03:00" into a ticket a month ahead of the outage.
cat > /usr/local/bin/check-cert-expiry <<'EOF'
#!/bin/bash
CERT="${1:-/etc/nginx/ssl/cert.pem}"
WARN_DAYS="${WARN_DAYS:-30}"
END_DATE=$(openssl x509 -in "$CERT" -noout -enddate 2>/dev/null | sed 's/notAfter=//')
if [ -z "$END_DATE" ]; then
  echo "CRITICAL: cannot read certificate $CERT"
  exit 2
fi
# openssl -checkend rather than `date -d "$END_DATE"`: -d is GNU-only and
# returns garbage on BSD/macOS, which would make this monitor cry wolf on a
# perfectly healthy certificate — the fastest way to get an alert ignored.
if ! openssl x509 -in "$CERT" -noout -checkend 0 >/dev/null 2>&1; then
  echo "CRITICAL: $CERT expired on $END_DATE"
  exit 2
fi
if ! openssl x509 -in "$CERT" -noout -checkend $((86400 * WARN_DAYS)) >/dev/null 2>&1; then
  echo "WARNING: $CERT expires within ${WARN_DAYS}d ($END_DATE) — renew now"
  exit 1
fi
echo "OK: $CERT valid beyond ${WARN_DAYS}d (expires $END_DATE)"
exit 0
EOF
chmod +x /usr/local/bin/check-cert-expiry

# Schedule it daily so the warning window is actually observed.
mkdir -p /etc/cron.d
cat > /etc/cron.d/cert-expiry <<'EOF'
# Daily TLS expiry check — alerts 30 days before the cert dies.
17 3 * * * root /usr/local/bin/check-cert-expiry /etc/nginx/ssl/cert.pem
EOF
chmod 644 /etc/cron.d/cert-expiry
