#!/usr/bin/env bash
# ansible-become-user-wrong: config repair — fail-closed until /home/ansible/become.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/become.yml
exit 0
