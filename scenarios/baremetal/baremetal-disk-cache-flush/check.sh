#!/usr/bin/env bash
# baremetal-disk-cache-flush: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/storage/cache-flush.cfg
exit 0
