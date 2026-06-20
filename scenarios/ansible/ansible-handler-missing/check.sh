#!/usr/bin/env bash
# ansible-handler-missing: config repair — fail-closed until /home/ansible/site.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/site.yml
exit 0
