#!/usr/bin/env bash
# linux-named-down: generic service health — fail-closed until the unit is active.
systemctl is-active named
exit 0
