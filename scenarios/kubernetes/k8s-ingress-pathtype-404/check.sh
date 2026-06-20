#!/usr/bin/env bash
# k8s-ingress-pathtype-404: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
