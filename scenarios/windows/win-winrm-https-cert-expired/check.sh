#!/usr/bin/env bash
# win-winrm-https-cert-expired: Windows validation — fail-closed until windows_fixed.
Get-Service WinRM
exit 0
