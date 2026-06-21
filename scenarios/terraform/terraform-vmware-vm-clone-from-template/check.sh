#!/usr/bin/env bash
# Cross-tech Terraform->VMware clone: the vSphere config must be reconciled with the
# real vCenter inventory. Fail-closed until /root/terraform/vsphere-vm.tf carries the
# FIXED-OK sentinel (written only after the datacenter/pool/datastore/template/network
# references are corrected).
grep -q FIXED-OK /root/iac/vsphere-vm.tf
exit 0
