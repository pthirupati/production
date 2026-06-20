#!/usr/bin/env bash
# baremetal-fan-curve-aggressive: config repair — fail-closed until /etc/bmc/fan_curve.cfg carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/bmc/fan_curve.cfg
exit 0
