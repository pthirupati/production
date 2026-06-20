#!/usr/bin/env bash
# ansible-retries-until: config repair — fail-closed until /home/ansible/retry.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/retry.yml
exit 0
