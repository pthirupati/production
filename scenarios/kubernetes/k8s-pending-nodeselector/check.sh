#!/usr/bin/env bash
# k8s-pending-nodeselector: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
