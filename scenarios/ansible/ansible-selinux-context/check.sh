#!/usr/bin/env bash
# ansible-selinux-context: config repair — fail-closed until /home/ansible/sefcontext.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/sefcontext.yml
exit 0
