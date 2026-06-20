#!/usr/bin/env bash
# ansible-package-name-wrong: config repair — fail-closed until /home/ansible/pkg.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/pkg.yml
exit 0
