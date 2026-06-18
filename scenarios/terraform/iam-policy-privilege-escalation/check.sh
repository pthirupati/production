#!/usr/bin/env bash
# Check: The IAM user policy does not grant iam:PassRole with a wildcard resource.
set -euo pipefail

IAM_USER="${IAM_USER:-lab-user}"

# Gather all inline policy documents for the user
POLICY_NAMES=$(aws iam list-user-policies --user-name "$IAM_USER" \
  --query 'PolicyNames[]' --output text 2>/dev/null)

FOUND_WILDCARD=false
for PNAME in $POLICY_NAMES; do
  DOC=$(aws iam get-user-policy --user-name "$IAM_USER" --policy-name "$PNAME" \
    --query 'PolicyDocument' --output json 2>/dev/null)

  # Check for PassRole with wildcard resource
  if echo "$DOC" | python3 -c "
import json, sys
doc = json.load(sys.stdin)
for stmt in doc.get('Statement', []):
    actions = stmt.get('Action', [])
    if isinstance(actions, str): actions = [actions]
    resource = stmt.get('Resource', '')
    if isinstance(resource, list): resource = ' '.join(resource)
    if any('PassRole' in a for a in actions) and '*' in resource:
        sys.exit(1)
sys.exit(0)
" 2>/dev/null; then
    : # no wildcard PassRole found in this policy
  else
    FOUND_WILDCARD=true
    echo "FAIL: Policy '$PNAME' still grants iam:PassRole with wildcard resource."
  fi
done

if $FOUND_WILDCARD; then
  exit 1
fi

echo "PASS: No wildcard iam:PassRole found for user '$IAM_USER'."
exit 0
