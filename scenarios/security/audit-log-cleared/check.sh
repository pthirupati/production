#!/bin/bash
# Check that auditd is configured with immutable mode
if ! systemctl is-active --quiet auditd 2>/dev/null; then
  echo "FAIL: auditd is not running — start with: systemctl start auditd"
  exit 1
fi
# Check for immutable flag (-e 2) in audit rules
IMMUTABLE=$(auditctl -l 2>/dev/null | grep -c '\-e 2')
if [ "$IMMUTABLE" -eq 0 ]; then
  # Also check rules files
  IMMUTABLE=$(grep -r '\-e 2' /etc/audit/rules.d/ /etc/audit/audit.rules 2>/dev/null | grep -v '^#' | wc -l)
fi
if [ "$IMMUTABLE" -eq 0 ]; then
  echo "FAIL: audit immutable mode (-e 2) not configured — add '-e 2' as the last line in /etc/audit/rules.d/99-immutable.rules"
  exit 1
fi
# Check max_log_file_action
LOG_ACTION=$(grep -E '^\s*max_log_file_action\s*=' /etc/audit/auditd.conf 2>/dev/null | awk -F= '{print $2}' | tr -d ' ')
if [ "$LOG_ACTION" = "rotate" ]; then
  echo "FAIL: max_log_file_action=rotate — logs can be overwritten. Change to keep_logs in /etc/audit/auditd.conf"
  exit 1
fi
echo "OK: auditd configured with immutable mode and log action: ${LOG_ACTION:-keep_logs}"
exit 0
