ui = false
disable_mlock = true

storage "file" {
  path = "/vault/data"
}

# Main API — accessible from all containers on fixitlab_net
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

# Prometheus metrics — localhost only (unauthenticated, internal only)
listener "tcp" {
  address     = "127.0.0.1:8201"
  tls_disable = 1
  telemetry {
    unauthenticated_metrics_access = true
  }
}

telemetry {
  prometheus_retention_time = "24h"
  disable_hostname            = true
}

# Advertise the internal Docker hostname so other containers can reach Vault
api_addr = "http://vault:8200"

default_lease_ttl = "768h"
max_lease_ttl     = "8760h"
