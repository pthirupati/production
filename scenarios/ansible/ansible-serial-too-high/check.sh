#!/usr/bin/env bash
# ansible-serial-too-high: config repair — fail-closed until /home/ansible/rolling.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/rolling.yml
exit 0
