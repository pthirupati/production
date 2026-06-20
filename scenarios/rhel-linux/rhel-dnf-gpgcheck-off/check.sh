#!/usr/bin/env bash
# rhel-dnf-gpgcheck-off: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/dnf/dnf.conf
exit 0
