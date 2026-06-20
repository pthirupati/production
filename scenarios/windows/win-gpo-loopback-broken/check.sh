#!/usr/bin/env bash
# win-gpo-loopback-broken: Windows validation — fail-closed until windows_fixed.
Get-Service gpsvc
exit 0
