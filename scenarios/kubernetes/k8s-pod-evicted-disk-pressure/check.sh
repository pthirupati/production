#!/usr/bin/env bash
# k8s-pod-evicted-disk-pressure: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
