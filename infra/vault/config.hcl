# HashiCorp Vault — single-node file storage (FixitLab production VPS)
# Bound to localhost; only the host and vault CLI/agent reach this port.

ui            = false
disable_mlock = true

storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}

api_addr     = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"

default_lease_ttl = "768h"
max_lease_ttl     = "8760h"
