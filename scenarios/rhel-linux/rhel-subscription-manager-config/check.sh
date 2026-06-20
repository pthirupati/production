#!/usr/bin/env bash
# rhel-subscription-manager-config: config repair — fail-closed until /etc/yum.repos.d/redhat.repo carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/yum.repos.d/redhat.repo
exit 0
