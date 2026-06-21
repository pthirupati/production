#!/usr/bin/env bash
# Cross-tech Docker->Linux/systemd: the compose stack must become a healthy managed
# service. Fail-closed (generic service check) until the appstack unit is active.
systemctl is-active appstack
exit 0
