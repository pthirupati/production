#!/usr/bin/env bash
# Cross-tech k8s-on-VMware: a DaemonSet pod is Pending because node worker-2 does
# not exist. Powering on the worker VM (k8s-worker-2) in VMware joins the node so
# the DaemonSet schedules its pod. Fail-closed until the node is Ready and every
# pod (DaemonSet included) is Running.
kubectl get nodes | grep -q Ready
kubectl get ds
kubectl get pods | grep -q Running
exit 0
