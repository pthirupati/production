#!/bin/bash
# Validation for "DNS Resolution Broken"
# The user must fix /etc/resolv.conf with valid DNS nameservers.

FAILED=0

# Check 1: resolv.conf must have valid nameservers (not the broken ones)
if grep -q '192.0.2.1' /etc/resolv.conf 2>/dev/null; then
    echo "FAIL: /etc/resolv.conf still has the broken nameserver 192.0.2.1"
    FAILED=1
fi
if grep -q '198.51.100.1' /etc/resolv.conf 2>/dev/null; then
    echo "FAIL: /etc/resolv.conf still has the broken nameserver 198.51.100.1"
    FAILED=1
fi

if [ $FAILED -eq 0 ]; then
    echo "OK: Broken nameservers have been replaced"
fi

# Check 2: DNS resolution must actually work
if nslookup google.com > /dev/null 2>&1; then
    echo "OK: DNS resolution works (google.com resolved successfully)"
else
    echo "FAIL: Cannot resolve domain names. Fix the nameservers in /etc/resolv.conf"
    FAILED=1
fi

# Check 3: Verify with a second domain
if nslookup github.com > /dev/null 2>&1; then
    echo "OK: github.com also resolves correctly"
else
    echo "WARN: github.com could not be resolved (may be a network issue)"
fi

if [ $FAILED -ne 0 ]; then
    echo ""
    echo "RESULT: DNS is still broken. Edit /etc/resolv.conf with valid nameservers."
    exit 1
fi

echo ""
echo "PASS: DNS resolution is working correctly!"
exit 0
