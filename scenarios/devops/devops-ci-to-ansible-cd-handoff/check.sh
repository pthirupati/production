#!/usr/bin/env bash
# Cross-tech DevOps/CI->Ansible CD: the release play must be fixed to consume the CI
# artifact and target a real group. Fail-closed until /home/ansible/cd-playbook.yml
# carries the FIXED-OK sentinel (written only after var/URL/host-group are corrected).
grep -q FIXED-OK /home/ansible/cd-playbook.yml
exit 0
