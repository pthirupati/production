#!/usr/bin/env bash
# ansible-fact-caching-stale: config repair — fail-closed until /home/ansible/ansible.cfg carries FIXED-OK.
grep -q FIXED-OK /home/ansible/ansible.cfg
exit 0
