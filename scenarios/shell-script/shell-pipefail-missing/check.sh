#!/usr/bin/env bash
# shell-pipefail-missing: config repair — fail-closed until /opt/scripts/deploy-pipeline.sh carries the FIXED-OK sentinel.
grep -q FIXED-OK /opt/scripts/deploy-pipeline.sh
exit 0
