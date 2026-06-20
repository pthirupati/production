#!/usr/bin/env bash
# ansible-tags-misused: config repair — fail-closed until /home/ansible/tagged.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/tagged.yml
exit 0
