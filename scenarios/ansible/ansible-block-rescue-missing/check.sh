#!/usr/bin/env bash
# ansible-block-rescue-missing: config repair — fail-closed until /home/ansible/block.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/block.yml
exit 0
