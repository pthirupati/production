#!/bin/bash
# Check that SNMP is no longer using 'public' community string
if grep -E '^\s*(rocommunity|rwcommunity|com2sec)\s+public\b' /etc/snmp/snmpd.conf 2>/dev/null | grep -qv '^#'; then
  echo "FAIL: SNMP community string 'public' is still configured in snmpd.conf — change it to a secure value"
  exit 1
fi
# Verify snmpd is running
if ! systemctl is-active --quiet snmpd 2>/dev/null; then
  echo "FAIL: snmpd is not running — start with: systemctl start snmpd"
  exit 1
fi
# Functional check: snmpwalk with 'public' should fail
if snmpwalk -c public -v2c -t 2 localhost .1.3 >/dev/null 2>&1; then
  echo "FAIL: SNMP still responds to 'public' community string — update snmpd.conf and restart snmpd"
  exit 1
fi
echo "OK: SNMP 'public' community string removed and service restarted"
exit 0
