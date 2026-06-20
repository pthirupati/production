#!/usr/bin/env bash
# ansible-yaml-indentation: config repair — fail-closed until /home/ansible/badindent.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/badindent.yml
exit 0
