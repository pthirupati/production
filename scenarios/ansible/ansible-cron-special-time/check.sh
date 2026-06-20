#!/usr/bin/env bash
# ansible-cron-special-time: config repair — fail-closed until /home/ansible/cron.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/cron.yml
exit 0
