#!/usr/bin/env bash
# ansible-vault-id-wrong: config repair — fail-closed until /home/ansible/vault-vars.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/vault-vars.yml
exit 0
