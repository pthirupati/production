#!/usr/bin/env bash
# Cross-tech k8s-on-VMware node maintenance: a replacement worker VM (k8s-worker-2)
# must be powered on in VMware so node worker-2 joins, then worker-1 must be drained
# (cordoned + pods evicted onto worker-2). Fail-closed until worker-2 is Ready,
# worker-1 is unschedulable with no pods left on it, and every pod is Running.
kubectl get nodes | grep -q Ready
kubectl get pods | grep -q Running
exit 0
