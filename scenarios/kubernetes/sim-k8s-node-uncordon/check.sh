#!/bin/bash
kubectl get nodes | grep -q Ready
kubectl get pods | grep -q Running
exit 0
