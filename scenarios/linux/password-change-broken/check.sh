#!/bin/bash
# Validation script for "Password Change Broken" scenario
# Checks that the PAM config is fixed and devuser can change password

PASS=true

# ── Step 1: PAM common-password references the correct module ──
if grep -q 'pam_unix\.so' /etc/pam.d/common-password && \
   ! grep -q 'pam_unixx\.so' /etc/pam.d/common-password; then
    echo "OK: PAM common-password has correct pam_unix.so module"
else
    echo "FAIL: PAM common-password is still broken (pam_unixx.so typo?)"
    PASS=false
fi

# ── Step 2: devuser account is not locked ──
SHADOW_HASH=$(getent shadow devuser | cut -d: -f2)
if echo "$SHADOW_HASH" | grep -q '^!'; then
    echo "FAIL: devuser account is still locked"
    PASS=false
else
    echo "OK: devuser account is unlocked"
fi

# ── Step 3: Can actually set a password for devuser ──
if echo "devuser:TestPass123" | chpasswd 2>/dev/null; then
    echo "OK: Password change succeeded for devuser"
else
    echo "FAIL: Cannot change password for devuser"
    PASS=false
fi

if [ "$PASS" = true ]; then
    echo ""
    echo "All checks passed — scenario solved!"
    exit 0
else
    echo ""
    echo "Some checks failed — keep investigating."
    exit 1
fi
