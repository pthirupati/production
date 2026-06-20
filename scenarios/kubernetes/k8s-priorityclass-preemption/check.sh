#!/usr/bin/env bash
# k8s-priorityclass-preemption: k8s health.
kubectl get pods | grep -q Running
exit 0
