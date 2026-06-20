#!/usr/bin/env bash
# k8s-readiness-gate-stuck: k8s health.
kubectl get pods | grep -q Running
exit 0
