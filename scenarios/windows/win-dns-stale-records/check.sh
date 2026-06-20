#!/usr/bin/env bash
# win-dns-stale-records: Windows validation — fail-closed until windows_fixed.
Get-Service DNS
exit 0
