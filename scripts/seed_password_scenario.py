#!/usr/bin/env python3
"""Seed the password-change-broken scenario via admin API."""
import requests
import json

BASE = "http://localhost:8080"

# Login as admin
r = requests.post(f"{BASE}/api/auth/login/", json={
    "email": "fixitlab.admin@gmail.com",
    "password": "Samatha@143"
})
token = r.json()["access"]
headers = {"Authorization": f"Bearer {token}"}

# Create the scenario
data = {
    "technology_id": 1,
    "slug": "password-change-broken",
    "title": "Password Change Broken",
    "subtitle": "A user cannot change their password",
    "category": "System Administration",
    "difficulty": "easy",
    "scenario_type": "fix",
    "description": (
        "A system administrator has reported that the user 'devuser' is unable to change "
        "their password on a production server. When attempting to use the passwd command, "
        "it fails with an error. Your task is to investigate why the password change mechanism "
        "is broken, fix the underlying issues, and verify that the user can successfully change "
        "their password. This scenario covers Linux PAM (Pluggable Authentication Modules) "
        "configuration and user account management - essential skills for any sysadmin."
    ),
    "objectives": [
        "Attempt to change the password for devuser and observe the error",
        "Investigate the PAM configuration in /etc/pam.d/",
        "Check if the user account is locked using passwd or shadow file",
        "Fix the PAM module reference and unlock the user account",
        "Verify the fix by running the validation script"
    ],
    "initial_state": (
        "An Ubuntu 22.04 server with a user 'devuser' already created. The PAM configuration "
        "for password changes has a typo - pam_unixx.so instead of pam_unix.so in "
        "/etc/pam.d/common-password. Additionally, the devuser account has been locked."
    ),
    "validation_script": (
        "#!/bin/bash\n"
        "PASS=true\n"
        "if grep -q 'pam_unix\\.so' /etc/pam.d/common-password && "
        "! grep -q 'pam_unixx\\.so' /etc/pam.d/common-password; then\n"
        "    echo \"OK: PAM common-password has correct pam_unix.so module\"\n"
        "else\n"
        "    echo \"FAIL: PAM common-password is still broken\"\n"
        "    PASS=false\n"
        "fi\n"
        "SHADOW_HASH=$(getent shadow devuser | cut -d: -f2)\n"
        "if echo \"$SHADOW_HASH\" | grep -q '^!'; then\n"
        "    echo \"FAIL: devuser account is still locked\"\n"
        "    PASS=false\n"
        "else\n"
        "    echo \"OK: devuser account is unlocked\"\n"
        "fi\n"
        "if echo \"devuser:TestPass123\" | chpasswd 2>/dev/null; then\n"
        "    echo \"OK: Password change succeeded\"\n"
        "else\n"
        "    echo \"FAIL: Cannot change password\"\n"
        "    PASS=false\n"
        "fi\n"
        "if [ \"$PASS\" = true ]; then exit 0; else exit 1; fi"
    ),
    "solution_explanation": (
        "Two issues prevented password changes:\n\n"
        "1. Corrupted PAM configuration: /etc/pam.d/common-password referenced pam_unixx.so "
        "instead of pam_unix.so. Fix with:\n"
        "   sed -i 's/pam_unixx.so/pam_unix.so/g' /etc/pam.d/common-password\n\n"
        "2. Locked user account: devuser was locked (! prefix in /etc/shadow). Fix with:\n"
        "   passwd -u devuser\n\n"
        "After both fixes, password changes work normally."
    ),
    "docker_image": "fixitlab/scenario-password-change-broken:latest",
    "infrastructure_type": "docker",
    "time_limit": 600,
    "max_score": 100,
    "is_free": True,
    "is_active": True
}

r = requests.post(f"{BASE}/api/admin/scenarios/", json=data, headers=headers)
print(f"Status: {r.status_code}")
result = r.json()
print(json.dumps(result, indent=2))

if r.status_code == 201:
    scenario_id = result["id"]
    print(f"\nScenario created with ID: {scenario_id}")

    # Add hints
    hints = [
        {"content": "Try running: passwd devuser — what error do you get?", "penalty": 5, "order": 1},
        {"content": "Check the PAM configuration: cat /etc/pam.d/common-password — look for any typos in module names", "penalty": 10, "order": 2},
        {"content": "Check if the account is locked: grep devuser /etc/shadow — a '!' prefix means locked. Use 'passwd -u devuser' to unlock.", "penalty": 15, "order": 3},
    ]
    for hint in hints:
        hr = requests.post(
            f"{BASE}/api/admin/scenarios/{scenario_id}/hints/",
            json=hint, headers=headers
        )
        print(f"  Hint '{hint['content'][:40]}...' -> {hr.status_code}")

    print("\nDone! Scenario seeded successfully.")
else:
    print(f"\nFailed to create scenario: {r.text}")
