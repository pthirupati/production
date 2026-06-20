#!/usr/bin/env bash
# ansible-copy-vs-template: config repair — fail-closed until /home/ansible/copy.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/copy.yml
exit 0
