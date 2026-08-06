#!/usr/bin/env bash
# Real-state: nvidia.com/gpu must be allocatable after GPU Operator / device plugin repair.
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu | grep -E '[[:space:]][1-9]'
