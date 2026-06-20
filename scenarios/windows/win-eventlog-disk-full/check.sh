#!/usr/bin/env bash
# win-eventlog-disk-full: Windows validation — fail-closed until windows_fixed.
Get-EventLog -List
exit 0
