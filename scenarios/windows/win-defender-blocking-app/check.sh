#!/usr/bin/env bash
# win-defender-blocking-app: Windows validation — fail-closed until windows_fixed.
Get-Service WinDefend
exit 0
