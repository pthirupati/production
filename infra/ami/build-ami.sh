#!/bin/bash
###############################################################################
# FixitLab Golden AMI Builder
#
# NOTE: this directory used to be named infra/packer/ but it is NOT Packer.
# There is no .pkr.hcl template. This is a plain bash builder that drives the
# AWS CLI directly (run-instances -> wait for user-data -> create-image ->
# terminate). Do not look for a Packer template or a `packer build` step in CI.
#
# Creates a pre-baked Ubuntu 22.04 AMI with all base packages already installed.
# This eliminates the 2-3 minute apt-get install during cloud-init, reducing
# EC2 lab boot time from ~3-4 minutes to ~30-40 seconds.
#
# Usage:
#   ./build-ami.sh                    # uses defaults (ap-south-1)
#   ./build-ami.sh us-east-1          # override region
#   AWS_PROFILE=myprofile ./build-ami.sh  # use specific AWS profile
#
# Prerequisites:
#   - AWS CLI v2 configured with credentials
#   - jq installed (brew install jq / apt install jq)
#   - SSH access to EC2 instances (key pair: fixitlab-labs)
#
# After building, set the new AMI ID in your .env file:
#   AWS_LAB_BASE_AMI=ami-0xxxxxxxxxxxx
###############################################################################
set -euo pipefail

# The user-data file is referenced by AWS CLI as a relative `file://` path, which
# resolves against the caller's cwd — not this script's location. Anchor to the
# script directory so `./infra/ami/build-ami.sh` from the repo root works.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REGION="${1:-ap-south-1}"
INSTANCE_TYPE="t3.micro"
KEY_PAIR="${AWS_LAB_KEY_PAIR:-fixitlab-labs}"
SECURITY_GROUP="${AWS_LAB_SECURITY_GROUP_ID:-}"
SUBNET="${AWS_LAB_SUBNET_ID:-}"

# Get the latest Ubuntu 22.04 LTS AMI for the region
echo "🔍 Finding latest Ubuntu 22.04 LTS AMI in ${REGION}..."
BASE_AMI=$(aws ec2 describe-images \
  --region "$REGION" \
  --owners 099720109477 \
  --filters \
    "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    "Name=state,Values=available" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text)

if [ -z "$BASE_AMI" ] || [ "$BASE_AMI" = "None" ]; then
  echo "❌ Could not find Ubuntu 22.04 AMI in region ${REGION}"
  exit 1
fi
echo "✅ Base AMI: ${BASE_AMI}"

# Build launch parameters
LAUNCH_PARAMS=(
  --region "$REGION"
  --image-id "$BASE_AMI"
  --instance-type "$INSTANCE_TYPE"
  --key-name "$KEY_PAIR"
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=fixitlab-ami-builder},{Key=Purpose,Value=ami-build}]"
)

[ -n "$SUBNET" ] && LAUNCH_PARAMS+=(--subnet-id "$SUBNET")
[ -n "$SECURITY_GROUP" ] && LAUNCH_PARAMS+=(--security-group-ids "$SECURITY_GROUP")

# Launch builder instance
echo "🚀 Launching builder instance..."
INSTANCE_ID=$(aws ec2 run-instances \
  "${LAUNCH_PARAMS[@]}" \
  --user-data "file://${SCRIPT_DIR}/golden-ami-userdata.sh" \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "✅ Builder instance: ${INSTANCE_ID}"
echo "⏳ Waiting for instance to start..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)
echo "✅ Instance running at ${PUBLIC_IP}"

# Wait for cloud-init to complete (the user-data script)
echo "⏳ Waiting for setup to complete (this takes 3-5 minutes)..."
echo "   You can monitor: ssh -i ~/.ssh/fixitlab-labs.pem ubuntu@${PUBLIC_IP} 'tail -f /var/log/cloud-init-output.log'"

MAX_WAIT=600  # 10 minutes
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  STATUS=$(aws ec2 describe-instance-status \
    --region "$REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'InstanceStatuses[0].InstanceStatus.Status' \
    --output text 2>/dev/null || echo "initializing")

  # Also check if our setup script finished
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
    -i ~/.ssh/fixitlab-labs.pem ubuntu@"$PUBLIC_IP" \
    "test -f /opt/fixitlab/.ami-ready" 2>/dev/null && break

  sleep 15
  ELAPSED=$((ELAPSED + 15))
  echo "   ...${ELAPSED}s elapsed (instance status: ${STATUS})"
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo "❌ Setup did not complete within ${MAX_WAIT}s. Check the instance manually."
  echo "   Instance: ${INSTANCE_ID} at ${PUBLIC_IP}"
  echo "   ssh -i ~/.ssh/fixitlab-labs.pem ubuntu@${PUBLIC_IP}"
  exit 1
fi

echo "✅ Setup complete!"

# Stop instance before creating AMI (cleaner snapshot)
echo "⏸️ Stopping instance..."
aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null
aws ec2 wait instance-stopped --region "$REGION" --instance-ids "$INSTANCE_ID"

# Create AMI
DATE=$(date +%Y%m%d)
AMI_NAME="fixitlab-golden-ubuntu-22.04-${DATE}"
echo "📸 Creating AMI: ${AMI_NAME}..."
NEW_AMI=$(aws ec2 create-image \
  --region "$REGION" \
  --instance-id "$INSTANCE_ID" \
  --name "$AMI_NAME" \
  --description "FixitLab pre-baked Ubuntu 22.04 with base packages for fast lab boot" \
  --tag-specifications "ResourceType=image,Tags=[{Key=Name,Value=${AMI_NAME}},{Key=fixitlab,Value=golden-ami},{Key=BuildDate,Value=${DATE}}]" \
  --query 'ImageId' \
  --output text)

echo "⏳ Waiting for AMI to be available..."
aws ec2 wait image-available --region "$REGION" --image-ids "$NEW_AMI"

# Terminate builder instance
echo "🗑️ Terminating builder instance..."
aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Golden AMI created successfully!"
echo ""
echo "   AMI ID:  ${NEW_AMI}"
echo "   Region:  ${REGION}"
echo "   Name:    ${AMI_NAME}"
echo ""
echo "   Update your .env file:"
echo "   AWS_LAB_BASE_AMI=${NEW_AMI}"
echo "═══════════════════════════════════════════════════════════════"
