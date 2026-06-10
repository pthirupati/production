#!/bin/bash
set -e
mkdir -p /etc/security/limits.d
if [ -f /etc/security/limits.d/99-nproc.conf ]; then
  sed -i 's/nproc[[:space:]]\+5/nproc 1024/g' /etc/security/limits.d/99-nproc.conf
else
  echo '* soft nproc 1024' > /etc/security/limits.d/99-nproc.conf
fi
grep -q 'nproc 1024' /etc/security/limits.d/99-nproc.conf || echo '* soft nproc 1024' >> /etc/security/limits.d/99-nproc.conf
