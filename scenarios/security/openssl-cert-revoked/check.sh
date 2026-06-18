#!/bin/bash
# Check that the CRL has been updated and nginx is configured to use it
CRL_FILE="/etc/nginx/ssl/ca.crl"
if [ ! -f "$CRL_FILE" ]; then
  echo "FAIL: CRL file not found at $CRL_FILE — download and install the new CRL"
  exit 1
fi
# Check the CRL is not older than 7 days
CRL_AGE=$(( ($(date +%s) - $(stat -c %Y "$CRL_FILE" 2>/dev/null || stat -f %m "$CRL_FILE" 2>/dev/null || echo 0)) / 86400 ))
if [ "$CRL_AGE" -gt 7 ]; then
  echo "FAIL: CRL file is $CRL_AGE days old — update it from the CA"
  exit 1
fi
# Verify CRL is valid PEM format
if ! openssl crl -in "$CRL_FILE" -noout 2>/dev/null; then
  echo "FAIL: CRL file is not valid PEM format — convert with: openssl crl -inform DER -in latest.crl -out $CRL_FILE"
  exit 1
fi
# Check nginx references the CRL
if grep -r 'ssl_crl' /etc/nginx/ 2>/dev/null | grep -q "$CRL_FILE\|ssl/ca.crl"; then
  if systemctl is-active --quiet nginx 2>/dev/null; then
    echo "OK: nginx CRL updated (age: ${CRL_AGE} days) and service is running"
    exit 0
  fi
fi
echo "FAIL: CRL file is valid but nginx is not configured to use it or not running — check ssl_crl directive"
exit 1
