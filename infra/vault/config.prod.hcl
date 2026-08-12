# Production-oriented Vault listener (TLS + mlock).
# Lab/dev keeps config.hcl (plaintext + disable_mlock) for local compose.
#
# Select with: VAULT_CONFIG=prod docker compose -f docker-compose.vault.yml up
# Requires certs at infra/vault/tls/vault.crt and vault.key (not committed).

ui = false
disable_mlock = false

storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = 0
  tls_cert_file = "/etc/vault/tls/vault.crt"
  tls_key_file  = "/etc/vault/tls/vault.key"
}

listener "tcp" {
  address     = "127.0.0.1:8203"
  tls_disable = 1
  telemetry {
    unauthenticated_metrics_access = true
  }
}

telemetry {
  prometheus_retention_time = "24h"
  disable_hostname          = true
}

api_addr     = "https://vault:8200"
cluster_addr = "https://127.0.0.1:8202"

default_lease_ttl = "768h"
max_lease_ttl     = "8760h"
