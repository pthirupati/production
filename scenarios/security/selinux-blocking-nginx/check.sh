#!/bin/bash
# Check that /srv/www has the correct SELinux context
if ! command -v getenforce >/dev/null 2>&1; then
  echo "FAIL: SELinux tools not available — this scenario requires a SELinux-enabled system"
  exit 1
fi
# Check if SELinux is enforcing
SELINUX_MODE=$(getenforce 2>/dev/null)
if [ "$SELINUX_MODE" = "Disabled" ]; then
  echo "FAIL: SELinux is disabled — this scenario requires SELinux in enforcing mode"
  exit 1
fi
# Check the file context on /srv/www
CONTEXT=$(ls -dZ /srv/www 2>/dev/null | awk '{print $1}')
if echo "$CONTEXT" | grep -q 'httpd_sys_content_t'; then
  # Verify nginx is serving files
  if curl -sf http://127.0.0.1/ >/dev/null 2>&1; then
    echo "OK: /srv/www has httpd_sys_content_t context and nginx is serving files"
    exit 0
  fi
  echo "OK: /srv/www has correct SELinux context httpd_sys_content_t"
  exit 0
fi
echo "FAIL: /srv/www has context '$CONTEXT' — apply httpd_sys_content_t with: semanage fcontext -a -t httpd_sys_content_t '/srv/www(/.)?' && restorecon -Rv /srv/www"
exit 1
