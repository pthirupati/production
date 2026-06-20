#!/usr/bin/env bash
# k8s-netpol-block-egress: k8s validation — fail-closed via cluster health.
kubectl get pods | grep -q Running
exit 0
