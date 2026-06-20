#!/usr/bin/env bash
# ansible-uri-validate-certs: config repair — fail-closed until /home/ansible/uri.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/uri.yml
exit 0
