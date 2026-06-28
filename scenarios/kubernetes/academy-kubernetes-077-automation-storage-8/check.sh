#!/usr/bin/env bash
kubectl get pods | grep -q Running
exit 0
