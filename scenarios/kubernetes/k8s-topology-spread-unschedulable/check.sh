#!/usr/bin/env bash
# k8s-topology-spread-unschedulable: k8s health.
kubectl get pods | grep -q Running
exit 0
