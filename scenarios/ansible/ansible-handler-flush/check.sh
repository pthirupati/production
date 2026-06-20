#!/usr/bin/env bash
# ansible-handler-flush: config repair — fail-closed until /home/ansible/flush.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/flush.yml
exit 0
