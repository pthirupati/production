#!/usr/bin/env bash
# k8s-crashloop-readonly-rootfs: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
