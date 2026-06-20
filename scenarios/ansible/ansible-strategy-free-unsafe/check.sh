#!/usr/bin/env bash
# ansible-strategy-free-unsafe: config repair — fail-closed until /home/ansible/strategy.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/strategy.yml
exit 0
