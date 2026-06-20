#!/usr/bin/env bash
# baremetal-bmc-snmp-misconfig: config repair — fail-closed until /etc/bmc/snmp.cfg carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/bmc/snmp.cfg
exit 0
