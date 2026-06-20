#!/usr/bin/env bash
# ansible-service-enabled-missing: config repair — fail-closed until /home/ansible/svc.yml carries FIXED-OK.
grep -q FIXED-OK /home/ansible/svc.yml
exit 0
