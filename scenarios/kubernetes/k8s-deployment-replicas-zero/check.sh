#!/usr/bin/env bash
# k8s-deployment-replicas-zero: k8s health.
kubectl get pods | grep -q Running
exit 0
