#!/bin/bash
# Check that the unauthorized module is unloaded
if lsmod 2>/dev/null | grep -q '^hidepid'; then
  echo "FAIL: hidepid module is still loaded — unload with: rmmod hidepid"
  exit 1
fi
# Check that the module file is removed
if [ -f /tmp/hidepid.ko ]; then
  echo "FAIL: module file /tmp/hidepid.ko still exists — remove it: rm /tmp/hidepid.ko"
  exit 1
fi
# Check for persistence via systemd
if systemctl is-enabled sysupdate.service 2>/dev/null | grep -q 'enabled'; then
  echo "FAIL: sysupdate.service persistence is still enabled — disable: systemctl disable sysupdate.service"
  exit 1
fi
# Check for incident report
if [ ! -f /tmp/incident-report.txt ] || [ "$(wc -c < /tmp/incident-report.txt)" -lt 20 ]; then
  echo "FAIL: /tmp/incident-report.txt missing or too short — document your findings"
  exit 1
fi
echo "OK: unauthorized kernel module removed, persistence cleaned, incident documented"
exit 0
