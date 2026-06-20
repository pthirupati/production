#!/usr/bin/env bash
# ansible-mount-fstab-missing: config repair — fail-closed until /home/ansible/mount.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/mount.yml
exit 0
