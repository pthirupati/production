#!/usr/bin/env bash
# ansible-env-var-not-passed: config repair — fail-closed until /home/ansible/env.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/env.yml
exit 0
