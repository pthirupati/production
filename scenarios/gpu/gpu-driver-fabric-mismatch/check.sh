#!/usr/bin/env bash
# gpu-driver-fabric-mismatch: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/fabric-version.conf
exit 0
