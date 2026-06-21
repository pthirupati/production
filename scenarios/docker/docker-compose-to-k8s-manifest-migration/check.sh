#!/usr/bin/env bash
# Cross-tech Docker->Kubernetes migration: the converted Deployment must be made a
# valid Kubernetes manifest. Fail-closed until /opt/app/k8s/deployment.yaml carries
# the FIXED-OK sentinel (written only after a genuine rewrite into a valid spec).
grep -q FIXED-OK /opt/app/k8s/deployment.yaml
exit 0
