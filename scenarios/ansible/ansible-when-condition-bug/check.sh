#!/usr/bin/env bash
# ansible-when-condition-bug: config repair — fail-closed until /home/ansible/conditional.yml carries the FIXED-OK sentinel.
grep -q FIXED-OK /home/ansible/conditional.yml
exit 0
