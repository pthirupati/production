#!/usr/bin/env bash
# Copy .env.production to your production server (run from laptop)
set -euo pipefail

PROD_HOST="${PROD_HOST:-64.227.175.89}"
PROD_USER="${PROD_USER:-root}"
ENV_FILE="${1:-.env.production}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — create it from env.production.example first"
  exit 1
fi

echo "Uploading $ENV_FILE → ${PROD_USER}@${PROD_HOST}:/opt/fixitlab/.env.production"
scp "$ENV_FILE" "${PROD_USER}@${PROD_HOST}:/opt/fixitlab/.env.production"
ssh "${PROD_USER}@${PROD_HOST}" "chmod 600 /opt/fixitlab/.env.production"
echo "Done. On server run: cd /opt/fixitlab && ./scripts/platform-start.sh"
