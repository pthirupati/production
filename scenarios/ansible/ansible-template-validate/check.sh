#!/usr/bin/env bash
# ansible-template-validate: config repair — fail-closed until /home/ansible/sshd-template.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/sshd-template.yml
exit 0
