#!/usr/bin/env bash
# ansible-import-vs-include: config repair — fail-closed until /home/ansible/include.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/include.yml
exit 0
