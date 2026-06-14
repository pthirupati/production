#!/usr/bin/env bash
# Verify Vault Prometheus metrics endpoint (port 8201).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx fixitlab_vault; then
  echo "[vault-metrics] Vault container not running — skipped"
  exit 0
fi

if docker run --rm --network container:fixitlab_vault curlimages/curl:8.5.0 -sf \
  "http://127.0.0.1:8201/v1/sys/metrics?format=prometheus" | head -c 400 | grep -q vault; then
  echo "[vault-metrics] Prometheus metrics OK"
  exit 0
fi

echo "ERROR: Vault metrics endpoint failed on :8201"
exit 1
