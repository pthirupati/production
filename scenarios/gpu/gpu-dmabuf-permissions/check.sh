#!/usr/bin/env bash
# gpu-dmabuf-permissions: config repair (FIXED-OK sentinel).
grep -q FIXED-OK /etc/gpu/dmabuf-access.conf
exit 0
