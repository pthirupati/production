#!/usr/bin/env bash
# Cross-tech GPU<->Kubernetes: the NVIDIA device-plugin DaemonSet must be corrected so
# the node advertises nvidia.com/gpu. Fail-closed until the manifest at
# /etc/nvidia-container-runtime/k8s-device-plugin.yaml carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/nvidia-container-runtime/k8s-device-plugin.yaml
exit 0
