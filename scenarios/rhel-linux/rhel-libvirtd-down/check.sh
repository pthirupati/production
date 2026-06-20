#!/usr/bin/env bash
# rhel-libvirtd-down: generic service health.
systemctl is-active libvirtd
exit 0
