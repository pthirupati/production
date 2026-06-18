#!/usr/bin/env bash
# Check: The private subnet route table has a 0.0.0.0/0 route pointing to a NAT Gateway.
set -euo pipefail

PRIVATE_SUBNET="${PRIVATE_SUBNET_ID:-}"

if [[ -z "$PRIVATE_SUBNET" ]]; then
  # Try to find a private subnet (no auto-assign public IP, no IGW route)
  PRIVATE_SUBNET=$(aws ec2 describe-subnets \
    --filters Name=mapPublicIpOnLaunch,Values=false \
    --query 'Subnets[0].SubnetId' \
    --output text 2>/dev/null || echo "")
fi

if [[ -z "$PRIVATE_SUBNET" || "$PRIVATE_SUBNET" == "None" ]]; then
  echo "FAIL: No private subnet found. Set PRIVATE_SUBNET_ID env var."
  exit 1
fi

RTB_ID=$(aws ec2 describe-route-tables \
  --filters "Name=association.subnet-id,Values=${PRIVATE_SUBNET}" \
  --query 'RouteTables[0].RouteTableId' \
  --output text 2>/dev/null || echo "")

if [[ -z "$RTB_ID" || "$RTB_ID" == "None" ]]; then
  echo "FAIL: No route table associated with private subnet '$PRIVATE_SUBNET'."
  exit 1
fi

NGW_ROUTE=$(aws ec2 describe-route-tables \
  --route-table-ids "$RTB_ID" \
  --query 'RouteTables[0].Routes[?DestinationCidrBlock==`0.0.0.0/0`&&starts_with(NatGatewayId,`nat-`)].NatGatewayId' \
  --output text 2>/dev/null || echo "")

if [[ -z "$NGW_ROUTE" || "$NGW_ROUTE" == "None" ]]; then
  echo "FAIL: Route table '$RTB_ID' has no 0.0.0.0/0 route to a NAT Gateway."
  exit 1
fi

echo "PASS: Route table '$RTB_ID' routes 0.0.0.0/0 via NAT Gateway '$NGW_ROUTE'."
exit 0
