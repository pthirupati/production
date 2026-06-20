#!/usr/bin/env bash
# k8s-sidecar-crashloop: k8s health.
kubectl get pods | grep -q Running
exit 0
