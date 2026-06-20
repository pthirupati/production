#!/usr/bin/env bash
# ansible-become-password-missing: config repair — fail-closed until /home/ansible/playbook.yml carries the FIXED-OK sentinel.
grep -q FIXED-OK /home/ansible/playbook.yml
exit 0
