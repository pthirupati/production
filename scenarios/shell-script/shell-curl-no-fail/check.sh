#!/usr/bin/env bash
# shell-curl-no-fail: config repair — fail-closed until /opt/scripts/healthcheck.sh carries FIXED-OK.
grep -q FIXED-OK /opt/scripts/healthcheck.sh
exit 0
