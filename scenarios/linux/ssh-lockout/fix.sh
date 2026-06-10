#!/bin/bash
set -e
chmod 600 /etc/ssh/ssh_host_rsa_key 2>/dev/null || true
sed -i 's/^Port .*/Port 22/' /etc/ssh/sshd_config 2>/dev/null || true
if ! grep -q '^Port 22' /etc/ssh/sshd_config 2>/dev/null; then
  echo 'Port 22' >> /etc/ssh/sshd_config
fi
if ! sshd -t 2>/dev/null; then
  cat > /etc/ssh/sshd_config <<'EOF'
Port 22
Protocol 2
HostKey /etc/ssh/ssh_host_rsa_key
PermitRootLogin yes
PasswordAuthentication yes
UsePAM yes
Subsystem sftp /usr/lib/openssh/sftp-server
EOF
fi
service ssh restart 2>/dev/null || service sshd restart 2>/dev/null || systemctl restart ssh 2>/dev/null || systemctl restart sshd 2>/dev/null || /usr/sbin/sshd
