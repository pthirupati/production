#!/usr/bin/env bash
# ansible-loop-wrong-var: config repair — fail-closed until /home/ansible/loop.yml carries the FIXED-OK sentinel.
grep -q FIXED-OK /home/ansible/loop.yml
exit 0
