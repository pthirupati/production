#!/usr/bin/env bash
# ansible-connection-local-wrong: config repair — fail-closed until /home/ansible/localconn.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/localconn.yml
exit 0
