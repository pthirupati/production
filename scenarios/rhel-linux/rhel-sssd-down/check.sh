#!/usr/bin/env bash
# rhel-sssd-down: generic service health.
systemctl is-active sssd
exit 0
