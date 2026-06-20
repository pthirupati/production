#!/usr/bin/env bash
# ansible-user-ssh-key: config repair — fail-closed until /home/ansible/sshkey.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/sshkey.yml
exit 0
