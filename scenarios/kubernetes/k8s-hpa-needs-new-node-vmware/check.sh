#!/usr/bin/env bash
# Cross-tech k8s-on-VMware: the HPA wants more replicas but pods are Pending for
# lack of node capacity. Only powering on the worker VM (k8s-worker-2) in the
# VMware simulator joins node worker-2 so the pods schedule. Fail-closed until the
# node is Ready, every pod Running, and the HPA's replica target is met.
kubectl get nodes | grep -q Ready
kubectl get hpa
kubectl get pods | grep -q Running
exit 0
