#!/bin/bash
set -e
sed -i '/^- : opsuser :/d' /etc/security/access.conf 2>/dev/null || true
grep -q '^+ : opsuser :' /etc/security/access.conf 2>/dev/null || echo '+ : opsuser : ALL' >> /etc/security/access.conf
