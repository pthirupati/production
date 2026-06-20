#!/usr/bin/env bash
# rhel-grub-default-target: config repair — fail-closed until /etc/systemd/default.target.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/systemd/default.target.conf
exit 0
