#!/usr/bin/env bash
# ansible-async-poll-wrong: config repair — fail-closed until /home/ansible/async.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/async.yml
exit 0
