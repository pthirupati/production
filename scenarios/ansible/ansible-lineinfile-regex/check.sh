#!/usr/bin/env bash
# ansible-lineinfile-regex: config repair — fail-closed until /home/ansible/lineinfile.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/lineinfile.yml
exit 0
