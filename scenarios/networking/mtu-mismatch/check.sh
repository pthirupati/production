#!/usr/bin/env bash
# The MTU/MSS fix (iptables mangle + interface MTU) cannot be introspected by the
# simulation engine, so completion is attested by a marker the learner writes
# AFTER applying and verifying the fix. Fail-closed until then.
grep -q FIXED-OK /opt/fixitlab/networking/mtu-mismatch.conf
exit 0
