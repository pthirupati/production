#!/bin/bash
set -e
rm -f /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend /var/cache/apt/archives/lock
DEBIAN_FRONTEND=noninteractive dpkg --configure -a
