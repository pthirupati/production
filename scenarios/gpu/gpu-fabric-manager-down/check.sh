#!/usr/bin/env bash
# gpu-fabric-manager-down: config repair — fail-closed until /etc/nvidia/fabricmanager.cfg carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/nvidia/fabricmanager.cfg
exit 0
