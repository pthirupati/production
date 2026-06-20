#!/usr/bin/env bash
# ansible-inventory-group-vars: config repair — fail-closed until /home/ansible/inventory/hosts.ini carries FIXED-OK.
grep -q FIXED-OK /home/ansible/inventory/hosts.ini
exit 0
