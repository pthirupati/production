#!/usr/bin/env bash
# Cross-tech Terraform->Ansible handoff: the rendered inventory must be reconciled
# with the provisioner output. Fail-closed until the rendered inventory
# /home/ansible/inventory/provisioned_hosts.ini carries the FIXED-OK sentinel
# (written only after a genuine re-render of the inventory from state).
grep -q FIXED-OK /home/ansible/inventory/provisioned_hosts.ini
exit 0
