#!/bin/bash
# Check that Ansible vault decryption is configured correctly
FAILED=0
ANSIBLE_CFG="/opt/ansible/ansible.cfg"
CORRECT_VAULT_PASS="/opt/ansible/.vault_pass"
SECRETS_FILE="/opt/ansible/vars/secrets.yml"

if [ ! -f "$ANSIBLE_CFG" ]; then
    echo "FAIL: ansible.cfg not found at $ANSIBLE_CFG"
    exit 1
fi

# Check that wrong path is gone
if grep -q '/etc/ansible/vault_pass' "$ANSIBLE_CFG"; then
    echo "FAIL: Old incorrect vault_password_file path still in ansible.cfg"
    FAILED=1
fi

# Check that correct path is set
if grep -q "vault_password_file.*$CORRECT_VAULT_PASS" "$ANSIBLE_CFG"; then
    echo "OK: vault_password_file correctly set to $CORRECT_VAULT_PASS"
else
    echo "FAIL: vault_password_file not set to $CORRECT_VAULT_PASS in ansible.cfg"
    FAILED=1
fi

# Check that vault password file actually exists
if [ -f "$CORRECT_VAULT_PASS" ]; then
    echo "OK: Vault password file exists at $CORRECT_VAULT_PASS"
else
    echo "FAIL: Vault password file missing at $CORRECT_VAULT_PASS"
    FAILED=1
fi

# Verify vault file can be decrypted
if command -v ansible-vault > /dev/null 2>&1 && [ -f "$SECRETS_FILE" ]; then
    if ansible-vault view "$SECRETS_FILE" --vault-password-file="$CORRECT_VAULT_PASS" > /dev/null 2>&1; then
        echo "OK: Vault file decrypts successfully"
    else
        echo "FAIL: ansible-vault view failed — vault file cannot be decrypted"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Ansible vault decryption configured correctly" && exit 0
exit 1
