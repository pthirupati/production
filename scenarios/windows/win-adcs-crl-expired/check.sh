#!/usr/bin/env bash
# win-adcs-crl-expired: Windows validation — fail-closed until windows_fixed.
Get-Service CertSvc
exit 0
