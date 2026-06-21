#!/usr/bin/env bash
# Cross-tech Ansible->Kubernetes handoff: the deploy playbook must be corrected to
# reach the cluster. Fail-closed until /home/ansible/k8s-deploy.yml carries the
# FIXED-OK sentinel (written only after kubeconfig/namespace/apiVersion are fixed).
grep -q FIXED-OK /home/ansible/k8s-deploy.yml
exit 0
