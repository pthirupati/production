#!/bin/bash
set -e
sed -i '/invalid\.ntp\.example/d' /etc/chrony/chrony.conf
service chrony restart 2>/dev/null || systemctl restart chrony 2>/dev/null || true
