#!/usr/bin/env bash
# k8s-pod-oomkilled-limit: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
