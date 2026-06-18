#!/bin/bash
# Check that NTP is synchronized and time is correct
SYNC_STATUS=$(timedatectl status 2>/dev/null)
if echo "$SYNC_STATUS" | grep -q 'synchronized: yes\|NTP synchronized: yes'; then
  echo "OK: system clock is NTP synchronized"
  exit 0
fi
# Check if the NTP server config no longer points to the broken server
if grep -q 'ntp.internal.corp' /etc/systemd/timesyncd.conf 2>/dev/null; then
  echo "FAIL: timesyncd still configured with unreachable NTP server 'ntp.internal.corp' — update to pool.ntp.org"
  exit 1
fi
# Check if timesyncd is running
if ! systemctl is-active --quiet systemd-timesyncd 2>/dev/null; then
  echo "FAIL: systemd-timesyncd is not running — start with: systemctl start systemd-timesyncd"
  exit 1
fi
echo "FAIL: NTP sync not confirmed — run: timedatectl set-ntp true && systemctl restart systemd-timesyncd"
exit 1
