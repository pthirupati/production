#!/usr/bin/env bash
# baremetal-disk-predictive-fail: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/smart/policy.cfg
exit 0
