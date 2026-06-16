ui = false
disable_mlock = true

storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "127.0.0.1:8200"
  tls_disable = 1
}

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

api_addr = "http://127.0.0.1:8200"

default_lease_ttl = "768h"
max_lease_ttl     = "8760h"
