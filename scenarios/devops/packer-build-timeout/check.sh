#!/bin/bash
# Check that Packer build timeout has been increased
FAILED=0
PACKER_TEMPLATE="/opt/packer/build.pkr.hcl"

# Try both .pkr.hcl and .json formats
if [ ! -f "$PACKER_TEMPLATE" ]; then
    PACKER_TEMPLATE="/opt/packer/build.json"
fi

if [ ! -f "$PACKER_TEMPLATE" ]; then
    echo "FAIL: Packer template not found at /opt/packer/build.pkr.hcl or /opt/packer/build.json"
    exit 1
fi

# Check old short timeout is gone
if grep -q 'ssh_timeout.*"5m"' "$PACKER_TEMPLATE"; then
    echo "FAIL: Old ssh_timeout of 5m still present — needs to be increased"
    FAILED=1
else
    echo "OK: Old 5m timeout removed"
fi

# Check new longer timeout is set (at least 20m, 30m, or 1h)
if grep -qE 'ssh_timeout.*"[2-9][0-9]m"|ssh_timeout.*"[1-9]h"' "$PACKER_TEMPLATE"; then
    TIMEOUT=$(grep -oE 'ssh_timeout.*"[0-9]+[mh]"' "$PACKER_TEMPLATE" | head -1)
    echo "OK: Timeout increased: $TIMEOUT"
else
    echo "FAIL: ssh_timeout not increased to at least 20m in packer template"
    FAILED=1
fi

# Check ssh_handshake_attempts is increased
if grep -qE 'ssh_handshake_attempts.*[2-9][0-9]|ssh_handshake_attempts.*[1-9][0-9]{2}' "$PACKER_TEMPLATE"; then
    echo "OK: ssh_handshake_attempts increased to adequate value"
else
    echo "WARN: ssh_handshake_attempts not found or not increased (optional but recommended)"
fi

# Validate Packer template
if command -v packer > /dev/null 2>&1; then
    if packer validate "$PACKER_TEMPLATE" > /dev/null 2>&1; then
        echo "OK: Packer template validates successfully"
    else
        echo "FAIL: Packer template validation failed"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Packer build timeout increased successfully" && exit 0
exit 1
