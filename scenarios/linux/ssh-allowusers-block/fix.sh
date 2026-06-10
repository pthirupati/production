#!/bin/bash
set -e
FILES="/etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf"
for f in $FILES; do
  [ -f "$f" ] || continue
  if grep -q '^AllowUsers' "$f"; then
    sed -i 's/^AllowUsers[[:space:]]\+adminonly/AllowUsers adminonly deploy/' "$f"
  fi
done
if ! grep -Rqs '^AllowUsers.*deploy' /etc/ssh/sshd_config /etc/ssh/sshd_config.d 2>/dev/null; then
  echo 'AllowUsers deploy' >> /etc/ssh/sshd_config
fi
service ssh restart 2>/dev/null || service sshd restart 2>/dev/null || systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || true
