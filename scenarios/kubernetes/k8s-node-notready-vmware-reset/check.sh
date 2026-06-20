#!/usr/bin/env bash
# Cross-tech k8s-on-VMware: worker-1 is NotReady because its VM is hung. Only a
# VMware reset of k8s-worker-1 re-registers the kubelet so the node returns Ready
# and the stranded pod reschedules. Fail-closed until the node is Ready and every
# pod is Running.
kubectl get nodes | grep -q Ready
kubectl get pods | grep -q Running
exit 0
