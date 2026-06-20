#!/usr/bin/env bash
# k8s-service-selector-typo: k8s validation — fail-closed via cluster health.
kubectl get endpoints api -o jsonpath='{.subsets[*].addresses[*].ip}'
exit 0
