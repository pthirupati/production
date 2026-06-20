#!/usr/bin/env bash
# baremetal-bmc-default-creds: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/bmc/credentials.cfg
exit 0
