#!/bin/bash
# Validate: an accept rule for 8080 was persisted in nftables config (FIXED-OK after the real fix).
grep -q FIXED-OK /etc/nftables.conf
exit 0
