#!/bin/bash
rm -f /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend /var/cache/apt/archives/lock /var/lib/apt/lists/lock
DEBIAN_FRONTEND=noninteractive dpkg --configure -a 2>/dev/null || true
rm -f /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend /var/cache/apt/archives/lock /var/lib/apt/lists/lock
if dpkg --audit 2>/dev/null | grep -q .; then
  DEBIAN_FRONTEND=noninteractive apt-get install -f -y 2>/dev/null || true
fi
