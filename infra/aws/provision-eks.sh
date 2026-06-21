#!/usr/bin/env bash
# FixitLab — AWS / EKS provisioning STUB (no-op until AWS keys exist).
#
# This is a SCAFFOLD. It NEVER provisions anything unless real AWS credentials
# are present AND APPLY=1 is set explicitly. By default it PRINTS what it WOULD
# do (VPC + subnets + EKS via eksctl or terraform) and exits 0. The default
# four-droplet pipeline never calls this script.
#
# Detection (any one satisfies "creds present"):
#   AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY   (static keys)
#   AWS_PROFILE                                  (shared-config profile)
#   AWS_ROLE_ARN + AWS_WEB_IDENTITY_TOKEN_FILE   (OIDC / IRSA)
#
# Backends (choose with EKS_PROVISIONER):
#   eksctl     (default)  — infra/aws/eksctl-cluster.yaml
#   terraform             — infra/terraform/main.tf (already in repo)
#
# Usage (scaffold / dry):   bash infra/aws/provision-eks.sh
# Usage (real, gated):      APPLY=1 EKS_PROVISIONER=eksctl bash infra/aws/provision-eks.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APPLY="${APPLY:-0}"
EKS_PROVISIONER="${EKS_PROVISIONER:-eksctl}"
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${EKS_CLUSTER_NAME:-fixitlab-eks}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

have_aws_creds() {
  if [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then return 0; fi
  if [ -n "${AWS_PROFILE:-}" ]; then return 0; fi
  if [ -n "${AWS_ROLE_ARN:-}" ] && [ -n "${AWS_WEB_IDENTITY_TOKEN_FILE:-}" ]; then return 0; fi
  return 1
}

echo "=== FixitLab AWS/EKS provisioning (SCAFFOLD) ==="
echo "  region=${AWS_REGION}  cluster=${CLUSTER_NAME}  provisioner=${EKS_PROVISIONER}  apply=${APPLY}"

if ! have_aws_creds; then
  echo "::notice::No AWS credentials detected — SCAFFOLD no-op."
  echo "Would, once AWS keys exist:"
  echo "  1. Create VPC (10.0.0.0/16) with public + private subnets across 3 AZs + NAT."
  echo "  2. Create EKS control plane (k8s 1.29) with two managed node groups:"
  echo "       app          (m5.xlarge,  on-demand, 2-50 nodes)"
  echo "       lab-runners  (m5.2xlarge, spot,      2-200 nodes, tainted workload=lab)"
  echo "  3. Provision RDS (Aurora PostgreSQL) + ElastiCache (Redis) in private subnets."
  echo "  4. Create ECR repos OR keep pulling images from Docker Hub."
  echo "  5. Write kubeconfig and deploy infra/k8s/overlays/eks."
  echo "Set AWS creds + APPLY=1 to run for real. See docs/AWS.md."
  exit 0
fi

echo "AWS credentials detected."
if ! _is_true "$APPLY"; then
  echo "APPLY not set — refusing to provision (safety). Re-run with APPLY=1 to proceed."
  echo "Planned backend: ${EKS_PROVISIONER}"
  exit 0
fi

case "$EKS_PROVISIONER" in
  eksctl)
    command -v eksctl >/dev/null 2>&1 || { echo "ERROR: eksctl not installed"; exit 1; }
    CFG="$ROOT/infra/aws/eksctl-cluster.yaml"
    echo "Provisioning via eksctl using $CFG ..."
    eksctl create cluster -f "$CFG"
    ;;
  terraform)
    command -v terraform >/dev/null 2>&1 || { echo "ERROR: terraform not installed"; exit 1; }
    echo "Provisioning via terraform in $ROOT/infra/terraform ..."
    terraform -chdir="$ROOT/infra/terraform" init
    terraform -chdir="$ROOT/infra/terraform" apply -auto-approve
    ;;
  *)
    echo "ERROR: unknown EKS_PROVISIONER=$EKS_PROVISIONER (use eksctl|terraform)"; exit 1
    ;;
esac

echo "=== EKS provisioning done ==="
