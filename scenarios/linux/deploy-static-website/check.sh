#!/bin/bash
FAILED=0
if [ -f /var/www/mysite/index.html ] && grep -qi '<h1' /var/www/mysite/index.html; then
  echo "OK: index.html exists"
else
  echo "FAIL: Create /var/www/mysite/index.html with an h1 tag"
  FAILED=1
fi
if nginx -t 2>/dev/null; then
  echo "OK: nginx config valid"
else
  echo "FAIL: nginx -t failed — configure site in sites-available/mysite"
  FAILED=1
fi
if pgrep nginx >/dev/null 2>&1 && curl -sf http://127.0.0.1/ | grep -qi '<h1'; then
  echo "OK: site is live"
else
  echo "FAIL: start nginx and ensure curl localhost returns your page"
  FAILED=1
fi
[ $FAILED -eq 0 ] && exit 0
exit 1
