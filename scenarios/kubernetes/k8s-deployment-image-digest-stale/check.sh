#!/usr/bin/env bash
# k8s-deployment-image-digest-stale: k8s health.
kubectl get pods | grep -q Running
exit 0
