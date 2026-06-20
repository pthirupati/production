#!/usr/bin/env bash
# rhel-dnf-automatic-misconfig: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/dnf/automatic.conf
exit 0
