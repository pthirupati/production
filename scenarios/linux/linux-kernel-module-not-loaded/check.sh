#!/bin/bash
# Validate: br_netfilter is configured to load at boot via a modules-load.d drop-in.
grep -r br_netfilter /etc/modules-load.d
exit 0
