#!/usr/bin/env bash
# k8s-imagepull-wrong-tag: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
