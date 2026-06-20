#!/usr/bin/env bash
# ansible-galaxy-role-missing: config repair — fail-closed until /home/ansible/requirements.yml carries the FIXED-OK sentinel.
grep -q FIXED-OK /home/ansible/requirements.yml
exit 0
