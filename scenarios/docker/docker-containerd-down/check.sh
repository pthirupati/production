#!/usr/bin/env bash
# docker-containerd-down: generic service health — fail-closed until the unit is active.
systemctl is-active containerd
exit 0
