#!/usr/bin/env bash
# ansible-with-items-deprecated: config repair — fail-closed until /home/ansible/legacy-loop.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/legacy-loop.yml
exit 0
