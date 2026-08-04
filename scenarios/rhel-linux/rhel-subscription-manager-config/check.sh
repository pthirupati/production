#!/usr/bin/env bash
# Entitlement must be Current and baseos repo enabled (subscription-manager refresh/attach).
set -euo pipefail
subscription-manager status 2>/dev/null | grep -qi 'Overall Status:[[:space:]]*Current'
subscription-manager repos --list 2>/dev/null | grep -A2 'rhel-9-for-x86_64-baseos-rpms' | grep -q 'Enabled:[[:space:]]*1'
grep -q 'rhel-9-for-x86_64-baseos-rpms' /etc/yum.repos.d/redhat.repo
grep -q 'enabled=1' /etc/yum.repos.d/redhat.repo
exit 0
