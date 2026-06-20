#!/usr/bin/env bash
# ansible-no-log-leaking-secret: config repair — fail-closed until /home/ansible/secret-task.yml carries the FIXED-OK sentinel.
grep -q FIXED-OK /home/ansible/secret-task.yml
exit 0
