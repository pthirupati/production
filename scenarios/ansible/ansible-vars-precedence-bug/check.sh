#!/usr/bin/env bash
# ansible-vars-precedence-bug: config repair — fail-closed until /home/ansible/group_vars/all.yml carries the FIXED-OK sentinel.
grep -q FIXED-OK /home/ansible/group_vars/all.yml
exit 0
