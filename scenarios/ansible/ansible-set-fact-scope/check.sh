#!/usr/bin/env bash
# ansible-set-fact-scope: config repair — fail-closed until /home/ansible/setfact.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/setfact.yml
exit 0
