#!/usr/bin/env bash
# Check: EKS node group IAM role has all three required managed policies attached.
set -euo pipefail

CLUSTER="${EKS_CLUSTER_NAME:-lab-cluster}"
NODEGROUP="${EKS_NODEGROUP_NAME:-lab-nodegroup}"

ROLE_ARN=$(aws eks describe-nodegroup \
  --cluster-name "$CLUSTER" \
  --nodegroup-name "$NODEGROUP" \
  --query 'nodegroup.nodeRole' \
  --output text 2>/dev/null || echo "")

if [[ -z "$ROLE_ARN" || "$ROLE_ARN" == "None" ]]; then
  echo "FAIL: Could not retrieve node group IAM role."
  exit 1
fi

ROLE_NAME="${ROLE_ARN##*/}"

ATTACHED=$(aws iam list-attached-role-policies \
  --role-name "$ROLE_NAME" \
  --query 'AttachedPolicies[].PolicyName' \
  --output text 2>/dev/null)

REQUIRED=("AmazonEKSWorkerNodePolicy" "AmazonEKS_CNI_Policy" "AmazonEC2ContainerRegistryReadOnly")
MISSING=()
for POLICY in "${REQUIRED[@]}"; do
  if ! echo "$ATTACHED" | grep -q "$POLICY"; then
    MISSING+=("$POLICY")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "FAIL: Node group role '$ROLE_NAME' is missing policies: ${MISSING[*]}"
  exit 1
fi

echo "PASS: Node group role '$ROLE_NAME' has all required EKS managed policies."
exit 0
