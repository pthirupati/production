#!/usr/bin/env bash
# Verify Vault Prometheus metrics endpoint (port 8201).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx fixitlab_vault; then
  echo "[vault-metrics] Vault container not running — skipped"
  exit 0
fi

_check_metrics() {
  docker run --rm --network container:fixitlab_vault curlimages/curl:8.5.0 -sf \
    "http://127.0.0.1:8201/v1/sys/metrics?format=prometheus" 2>/dev/null \
    | head -c 400 | grep -q vault
}

if _check_metrics; then
  echo "[vault-metrics] Prometheus metrics OK"
  exit 0
fi

echo "[vault-metrics] Metrics not ready — recreating Vault with latest config..."
chmod +x "$ROOT/scripts/vault/"*.sh 2>/dev/null || true
vault_compose up -d --force-recreate vault
bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true
bash "$ROOT/scripts/vault/ensure-network.sh" 2>/dev/null || true
sleep 3

if _check_metrics; then
  echo "[vault-metrics] Prometheus metrics OK (after recreate)"
  exit 0
fi

echo "ERROR: Vault metrics endpoint failed on :8201"
exit 1
