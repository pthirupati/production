#!/bin/bash
set -e
rm -f /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend /var/cache/apt/archives/lock
dpkg --configure -a 2>/dev/null || true
