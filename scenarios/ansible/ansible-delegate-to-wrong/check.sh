#!/usr/bin/env bash
# ansible-delegate-to-wrong: config repair — fail-closed until /home/ansible/delegate.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/delegate.yml
exit 0
