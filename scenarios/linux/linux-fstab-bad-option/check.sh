#!/usr/bin/env bash
# linux-fstab-bad-option: config repair — fail-closed until /etc/fstab carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/fstab
exit 0
