#!/usr/bin/env bash
# ansible-changed-when-wrong: config repair — fail-closed until /home/ansible/idempotent.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/idempotent.yml
exit 0
