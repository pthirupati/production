#!/usr/bin/env bash
# Roll back single-droplet production to previous commit and redeploy.
set -euo pipefail

HOST="${1:-}"
if [ -z "$HOST" ]; then
  echo "Usage: $0 <droplet-ip-or-host>"
  exit 1
fi

echo "Rolling back single-droplet on $HOST to HEAD~1..."
ssh -o StrictHostKeyChecking=accept-new "root@${HOST}" bash -s <<'REMOTE'
set -euo pipefail
cd /opt/fixitlab || cd /root/fixitlab || { echo "Repo not found"; exit 1; }
git fetch origin main
git reset --hard HEAD~1
bash scripts/ci-remote-platform.sh deploy
REMOTE
echo "Rollback complete."
