#!/bin/bash
# Validation for "SSH Configuration Lockout"
# The user must:
#   1. Remove the invalid option from sshd_config
#   2. Change port back to 22
#   3. Fix host key permissions (chmod 600)
#   4. Start sshd

FAILED=0

# Check 1: sshd config must be valid
if ! sshd -t 2>/dev/null; then
    echo "FAIL: sshd configuration has errors. Run 'sshd -t' to see them."
    FAILED=1
else
    echo "OK: sshd configuration syntax is valid"
fi

# Check 2: Host key permissions must be 600
PERMS=$(stat -c %a /etc/ssh/ssh_host_rsa_key 2>/dev/null)
if [ "$PERMS" != "600" ]; then
    echo "FAIL: ssh_host_rsa_key permissions are $PERMS, must be 600"
    FAILED=1
else
    echo "OK: Host key permissions are correct (600)"
fi

# Check 3: sshd must be running
if ! pgrep -x sshd > /dev/null 2>&1; then
    echo "FAIL: sshd is not running. Start it after fixing the config."
    FAILED=1
else
    echo "OK: sshd process is running"
fi

# Check 4: Port 22 must be listening
if ! ss -tlnp 2>/dev/null | grep -q ":22 "; then
    echo "FAIL: sshd is not listening on port 22"
    FAILED=1
else
    echo "OK: sshd is listening on port 22"
fi

if [ $FAILED -ne 0 ]; then
    echo ""
    echo "RESULT: Not all checks passed. Keep trying!"
    exit 1
fi

echo ""
echo "PASS: SSH is properly configured and running on port 22!"
exit 0
