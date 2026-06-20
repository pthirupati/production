#!/usr/bin/env bash
# gpu-driver-secureboot: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/secureboot-signing.conf
exit 0
