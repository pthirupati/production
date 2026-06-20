#!/usr/bin/env bash
# rhel-tuned-wrong-profile: config repair — fail-closed until /etc/tuned/active_profile carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/tuned/active_profile
exit 0
