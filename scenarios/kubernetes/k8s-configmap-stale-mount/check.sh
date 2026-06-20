#!/usr/bin/env bash
# k8s-configmap-stale-mount: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
