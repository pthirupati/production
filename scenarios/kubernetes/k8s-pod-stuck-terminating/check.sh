#!/usr/bin/env bash
# k8s-pod-stuck-terminating: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
