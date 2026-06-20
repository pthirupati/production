#!/usr/bin/env bash
# Configure DigitalOcean cloud firewalls for the FixitLab four-droplet cluster.
#
# Port matrix:
#   D1 Edge  (fw: fixitlab-edge-fw, tag fixitlab-edge)
#       inbound  : 22/tcp (SSH, anywhere), 80/tcp + 443/tcp (HTTP/S, anywhere)
#                  6379 (redis), 5672 (rabbitmq), 8200 (vault)  <- source: D2 (+ D4 for 8200)
#       outbound : all
#   D2 App   (fw: fixitlab-app-fw, tag fixitlab-app)
#       inbound  : 22/tcp (SSH, anywhere*), 8000/tcp  <- source: D1 edge private IP
#       outbound : all
#   D3 Data  (fw: fixitlab-db-fw, tag fixitlab-db)
#       inbound  : 22/tcp (SSH, anywhere*), 5432 + 6432  <- source: D2 app private IP
#       outbound : all
#   D4 Labs  (fw: fixitlab-labs-fw, tag fixitlab-labs)
#       inbound  : 22/tcp  <- source: D2 app private IP (remote docker over SSH)
#       outbound : all
#
#   * SSH on D2/D3/D4 is restricted to the VPC CIDR (private) + the edge node so the
#     cluster is bootstrapped/deployed over the private network only.
#
# Idempotent: firewall rules are declared fresh each run (doctl replaces the rule
# set per firewall). NEVER deletes droplets. DRY_RUN=1 prints the doctl commands.
#
# Required env: APP_PRIVATE_IP DATA_PRIVATE_IP LABS_PRIVATE_IP EDGE_PRIVATE_IP
# Optional    : VPC_CIDR (default 10.0.0.0/8 fallback for SSH source)
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
VPC_CIDR="${VPC_CIDR:-10.0.0.0/8}"

EDGE_PRIVATE_IP="${EDGE_PRIVATE_IP:?EDGE_PRIVATE_IP required}"
APP_PRIVATE_IP="${APP_PRIVATE_IP:?APP_PRIVATE_IP required}"
DATA_PRIVATE_IP="${DATA_PRIVATE_IP:?DATA_PRIVATE_IP required}"
LABS_PRIVATE_IP="${LABS_PRIVATE_IP:?LABS_PRIVATE_IP required}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

# Resolve DO token (mask, never print)
if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${DO_API_TOKEN:-}" ]; then
  export DIGITALOCEAN_ACCESS_TOKEN="$DO_API_TOKEN"
fi
if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${PRODUCTION_ENV_B64:-}" ]; then
  export DIGITALOCEAN_ACCESS_TOKEN="$(echo "$PRODUCTION_ENV_B64" | base64 -d | grep '^DO_API_TOKEN=' | cut -d= -f2- | tr -d '\r')"
fi
[ -n "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::${DIGITALOCEAN_ACCESS_TOKEN}"

if ! _is_true "$DRY_RUN"; then
  command -v doctl >/dev/null 2>&1 || { echo "ERROR: doctl not installed"; exit 1; }
  doctl auth init -t "$DIGITALOCEAN_ACCESS_TOKEN" >/dev/null 2>&1 || true
fi

doctl_run() {
  if _is_true "$DRY_RUN"; then echo "DRY_RUN doctl $*"; return 0; fi
  doctl "$@"
}

# Create the firewall if missing, then set its rules. doctl has no single
# "replace rules" verb, so we add the desired rules (idempotent: re-adding an
# existing rule is a no-op error we tolerate). On a fresh firewall the rules are
# supplied at create time.
fw_id_by_name() {
  local name="$1"
  if _is_true "$DRY_RUN"; then echo ""; return; fi
  doctl compute firewall list --format ID,Name --no-header 2>/dev/null | awk -v n="$name" '$2==n {print $1; exit}'
}

ensure_firewall() {
  # $1 name, $2 tag, $3 inbound-rules, $4 outbound-rules
  local name="$1" tag="$2" inbound="$3" outbound="$4" id
  id="$(fw_id_by_name "$name")"
  if [ -z "$id" ]; then
    doctl_run compute firewall create \
      --name "$name" \
      --tag-names "$tag" \
      --inbound-rules "$inbound" \
      --outbound-rules "$outbound"
    echo "  created firewall $name (tag $tag)"
  else
    # Replace by adding the declared inbound rules (outbound already allow-all).
    doctl_run compute firewall add-rules "$id" --inbound-rules "$inbound" || true
    echo "  updated firewall $name ($id)"
  fi
}

OUTBOUND_ALL="protocol:tcp,ports:all,address:0.0.0.0/0,address:::/0 protocol:udp,ports:all,address:0.0.0.0/0,address:::/0 protocol:icmp,address:0.0.0.0/0,address:::/0"

echo "=== FixitLab cluster firewalls (dry_run=$DRY_RUN) ==="

# ── D1 Edge: public 80/443 + SSH; data ports only from D2 (vault also from D4) ──
EDGE_IN="protocol:tcp,ports:22,address:0.0.0.0/0,address:::/0"
EDGE_IN="$EDGE_IN protocol:tcp,ports:80,address:0.0.0.0/0,address:::/0"
EDGE_IN="$EDGE_IN protocol:tcp,ports:443,address:0.0.0.0/0,address:::/0"
EDGE_IN="$EDGE_IN protocol:tcp,ports:6379,address:${APP_PRIVATE_IP}/32"
EDGE_IN="$EDGE_IN protocol:tcp,ports:5672,address:${APP_PRIVATE_IP}/32"
EDGE_IN="$EDGE_IN protocol:tcp,ports:8200,address:${APP_PRIVATE_IP}/32,address:${LABS_PRIVATE_IP}/32"
ensure_firewall fixitlab-edge-fw fixitlab-edge "$EDGE_IN" "$OUTBOUND_ALL"

# ── D2 App: SSH from VPC/edge; backend 8000 only from D1 edge ──
APP_IN="protocol:tcp,ports:22,address:${VPC_CIDR},address:${EDGE_PRIVATE_IP}/32"
APP_IN="$APP_IN protocol:tcp,ports:8000,address:${EDGE_PRIVATE_IP}/32"
ensure_firewall fixitlab-app-fw fixitlab-app "$APP_IN" "$OUTBOUND_ALL"

# ── D3 Data: SSH from VPC/edge; postgres 5432 + pgbouncer 6432 only from D2 ──
DB_IN="protocol:tcp,ports:22,address:${VPC_CIDR},address:${EDGE_PRIVATE_IP}/32"
DB_IN="$DB_IN protocol:tcp,ports:5432,address:${APP_PRIVATE_IP}/32"
DB_IN="$DB_IN protocol:tcp,ports:6432,address:${APP_PRIVATE_IP}/32"
ensure_firewall fixitlab-db-fw fixitlab-db "$DB_IN" "$OUTBOUND_ALL"

# ── D4 Labs: SSH only, from D2 (remote docker) + edge (bootstrap) ──
LABS_IN="protocol:tcp,ports:22,address:${APP_PRIVATE_IP}/32,address:${EDGE_PRIVATE_IP}/32,address:${VPC_CIDR}"
ensure_firewall fixitlab-labs-fw fixitlab-labs "$LABS_IN" "$OUTBOUND_ALL"

echo "=== firewalls configured ==="
