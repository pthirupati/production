#!/usr/bin/env bash
# rhel-nfs-server-down: generic service health — fail-closed until the unit is active.
systemctl is-active nfs-server
exit 0
