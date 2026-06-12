#!/bin/bash
# Validation script for "Fix Broken User Creation"
# Exit 0 = pass, Exit 1 = fail

SCORE=0
TOTAL=5

# Helper: portable stat (Linux vs macOS)
get_perm() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null; }

# Step 1: Check /etc/passwd is readable and valid
if command -v pwck &>/dev/null; then
    pwck -r -q 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "FAIL: /etc/passwd has integrity errors. Run 'pwck' to check."
        exit 1
    fi
else
    # Fallback: check no obviously corrupted lines exist
    if grep -q 'CORRUPTED:::ENTRY' /etc/passwd 2>/dev/null; then
        echo "FAIL: /etc/passwd contains corrupted entries"
        exit 1
    fi
fi
echo "OK: /etc/passwd integrity check passed"
SCORE=$((SCORE + 1))

# Step 2: Check /etc/group is valid
if command -v grpck &>/dev/null; then
    grpck -r -q 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "FAIL: /etc/group has integrity errors. Run 'grpck' to check."
        exit 1
    fi
else
    # Fallback: check for known bad entries
    if grep -q 'fakegroup' /etc/group 2>/dev/null; then
        echo "FAIL: /etc/group contains invalid entries"
        exit 1
    fi
fi
echo "OK: /etc/group integrity check passed"
SCORE=$((SCORE + 1))

# Step 3: Check permissions on critical files
PASSWD_PERM=$(get_perm /etc/passwd)
SHADOW_PERM=$(get_perm /etc/shadow)
GROUP_PERM=$(get_perm /etc/group)

if [ "$PASSWD_PERM" = "777" ] || [ "$PASSWD_PERM" = "666" ]; then
    echo "FAIL: /etc/passwd is still world-writable ($PASSWD_PERM) — run chmod 644 /etc/passwd"
    exit 1
fi
if [ "$PASSWD_PERM" != "644" ]; then
    echo "FAIL: /etc/passwd has wrong permissions ($PASSWD_PERM, expected 644)"
    exit 1
fi
if [ "$SHADOW_PERM" != "640" ] && [ "$SHADOW_PERM" != "600" ]; then
    echo "FAIL: /etc/shadow has wrong permissions ($SHADOW_PERM, expected 640)"
    exit 1
fi
if [ "$GROUP_PERM" != "644" ]; then
    echo "FAIL: /etc/group has wrong permissions ($GROUP_PERM, expected 644)"
    exit 1
fi
# Check lock file is removed
if [ -f /etc/.pwd.lock ]; then
    echo "FAIL: /etc/.pwd.lock still exists — remove it to unblock useradd"
    exit 1
fi
echo "OK: File permissions are correct and lock file removed"
SCORE=$((SCORE + 1))

# Step 4: Check user 'devops' exists with home directory and bash shell
if ! id devops &>/dev/null; then
    echo "FAIL: User 'devops' does not exist. Create it with: useradd -m -s /bin/bash devops"
    exit 1
fi
DEVOPS_SHELL=$(getent passwd devops | cut -d: -f7)
DEVOPS_HOME=$(getent passwd devops | cut -d: -f6)
if [ "$DEVOPS_SHELL" != "/bin/bash" ]; then
    echo "FAIL: User 'devops' has shell '$DEVOPS_SHELL' instead of '/bin/bash'"
    exit 1
fi
if [ ! -d "$DEVOPS_HOME" ]; then
    echo "FAIL: Home directory '$DEVOPS_HOME' does not exist for user 'devops'"
    exit 1
fi
echo "OK: User 'devops' exists with bash shell and home directory"
SCORE=$((SCORE + 1))

# Step 5: Verify useradd works now (create a test user)
useradd -m -s /bin/bash fixitlab_testuser 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: useradd still not working — cannot create new users"
    exit 1
fi
# Clean up test user
userdel -r fixitlab_testuser 2>/dev/null
echo "OK: useradd command is working correctly"
SCORE=$((SCORE + 1))

echo ""
echo "PASS: All checks passed ($SCORE/$TOTAL)"
echo "User management is fully restored and 'devops' user is created."
exit 0
