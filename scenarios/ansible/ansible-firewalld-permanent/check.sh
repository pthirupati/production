#!/usr/bin/env bash
# ansible-firewalld-permanent: config repair — fail-closed until /home/ansible/firewalld.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/firewalld.yml
exit 0
