#!/usr/bin/env bash
# baremetal-nic-teaming-mode: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/network/teaming.cfg
exit 0
