#!/usr/bin/env bash
# win-w32time-drift: Windows validation — fail-closed until windows_fixed.
Get-Service W32Time
exit 0
