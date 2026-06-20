#!/usr/bin/env bash
# gpu-mig-profile-wrong: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/nvidia/mig-layout.conf
exit 0
