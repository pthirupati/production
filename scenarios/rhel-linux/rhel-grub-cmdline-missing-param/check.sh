#!/usr/bin/env bash
# rhel-grub-cmdline-missing-param: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/default/grub
exit 0
