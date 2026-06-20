#!/usr/bin/env bash
# ansible-failed-when-wrong: config repair — fail-closed until /home/ansible/failwhen.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/failwhen.yml
exit 0
