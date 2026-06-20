#!/usr/bin/env bash
# Create the FixitLab four-droplet cluster: one VPC + 4 tagged droplets, wait for SSH.
#
#   D1 fixitlab-edge   (public)  tag: fixitlab-edge
#   D2 fixitlab-app    (private) tag: fixitlab-app
#   D3 fixitlab-db     (private) tag: fixitlab-db
#   D4 fixitlab-labs   (private) tag: fixitlab-labs
#
# Idempotent: reuses droplets/VPC that already exist (matched by name). NEVER
# destroys anything. Honors DO_PROTECTED_DROPLET_IDS (refuses to touch them).
#
# DRY_RUN=1 prints every doctl/ssh command instead of running it.
# WIRE_EXISTING=1 discovers droplets by tag and skips creation entirely.
#
# Requires: doctl (DIGITALOCEAN_ACCESS_TOKEN or DO_API_TOKEN / PRODUCTION_ENV_B64),
#           PROD_SSH_KEY (private key for root SSH).
#
# Outputs (GITHUB_OUTPUT + stdout):
#   edge_id app_id db_id labs_id
#   edge_public_ip edge_private_ip app_private_ip db_private_ip labs_private_ip
#   vpc_id
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

DO_REGION="${DO_REGION:-blr1}"
DO_SIZE="${DO_SIZE:-s-2vcpu-8gb-160gb-intel}"
IMAGE="${DO_IMAGE:-ubuntu-22-04-x64}"
VPC_NAME="${VPC_NAME:-fixitlab-vpc}"
DRY_RUN="${DRY_RUN:-0}"
WIRE_EXISTING="${WIRE_EXISTING:-0}"

EDGE_NAME="${EDGE_NAME:-fixitlab-edge}"
APP_NAME="${APP_NAME:-fixitlab-app}"
DB_NAME="${DB_NAME:-fixitlab-db}"
LABS_NAME="${LABS_NAME:-fixitlab-labs}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

# ── doctl wrapper: print in DRY_RUN, execute otherwise ──
doctl_run() {
  if _is_true "$DRY_RUN"; then
    echo "DRY_RUN doctl $*"
    return 0
  fi
  doctl "$@"
}

emit_output() {
  local key="$1" val="$2"
  echo "${key}=${val}"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "${key}=${val}" >> "$GITHUB_OUTPUT"; fi
}

# ── Resolve DO token ──
if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${DO_API_TOKEN:-}" ]; then
  export DIGITALOCEAN_ACCESS_TOKEN="$DO_API_TOKEN"
fi
if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${PRODUCTION_ENV_B64:-}" ]; then
  export DIGITALOCEAN_ACCESS_TOKEN="$(echo "$PRODUCTION_ENV_B64" | base64 -d | grep '^DO_API_TOKEN=' | cut -d= -f2- | tr -d '\r')"
fi
# Never echo the token; mask it for GitHub.
if [ -n "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${GITHUB_ACTIONS:-}" ]; then
  echo "::add-mask::${DIGITALOCEAN_ACCESS_TOKEN}"
fi

if ! _is_true "$DRY_RUN"; then
  if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ]; then
    echo "ERROR: Set DO_API_TOKEN or PRODUCTION_ENV_B64 with DO_API_TOKEN"; exit 1
  fi
  command -v doctl >/dev/null 2>&1 || { echo "ERROR: doctl not installed"; exit 1; }
  doctl auth init -t "$DIGITALOCEAN_ACCESS_TOKEN" >/dev/null 2>&1 || true
fi

case "$DO_SIZE" in s-2vcpu-8gb) DO_SIZE="s-2vcpu-8gb-160gb-intel";; esac

# ── Resolve SSH key id from PROD_SSH_KEY (reused logic from single-droplet) ──
resolve_ssh_key_id() {
  if [ -n "${DO_SSH_KEY_ID:-}" ]; then echo "$DO_SSH_KEY_ID"; return; fi
  if _is_true "$DRY_RUN"; then echo "<SSH_KEY_ID>"; return; fi
  [ -n "${PROD_SSH_KEY:-}" ] || { echo "ERROR: set DO_SSH_KEY_ID or PROD_SSH_KEY" >&2; exit 1; }
  local kf pf fp id
  kf="$(mktemp)"; pf="$(mktemp)"
  printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$kf"; chmod 600 "$kf"
  ssh-keygen -y -f "$kf" > "$pf" 2>/dev/null || { echo "ERROR: PROD_SSH_KEY invalid" >&2; rm -f "$kf" "$pf"; exit 1; }
  fp="$(ssh-keygen -lf "$pf" -E md5 | awk '{print $2}' | sed 's/MD5://')"
  id="$(doctl compute ssh-key list --format ID,FingerPrint --no-header | awk -v f="$fp" '$2==f {print $1; exit}')"
  if [ -z "$id" ]; then
    doctl compute ssh-key import "fixitlab-ci-$(date +%Y%m%d)" --public-key-file "$pf" >/dev/null
    id="$(doctl compute ssh-key list --format ID,FingerPrint --no-header | awk -v f="$fp" '$2==f {print $1; exit}')"
  fi
  rm -f "$kf" "$pf"
  echo "$id"
}

droplet_id_by_name() {
  local name="$1"
  if _is_true "$DRY_RUN"; then echo ""; return; fi
  doctl compute droplet list --format ID,Name --no-header | awk -v n="$name" '$2==n {print $1; exit}'
}

droplet_id_by_tag() {
  local tag="$1"
  doctl compute droplet list --tag-name "$tag" --format ID --no-header 2>/dev/null | head -n1
}

assert_not_protected() {
  local id="$1"
  local protected="${DO_PROTECTED_DROPLET_IDS:-}"
  [ -n "$protected" ] || return 0
  for p in ${protected//,/ }; do
    if [ "$p" = "$id" ]; then
      echo "ERROR: droplet $id is in DO_PROTECTED_DROPLET_IDS — refusing to modify"; exit 1
    fi
  done
}

# ── VPC ──
ensure_vpc() {
  local vid
  if _is_true "$WIRE_EXISTING"; then
    vid="$(doctl vpcs list --format ID,Name --no-header 2>/dev/null | awk -v n="$VPC_NAME" '$2==n {print $1; exit}')"
    echo "$vid"; return
  fi
  if _is_true "$DRY_RUN"; then
    doctl_run vpcs create --name "$VPC_NAME" --region "$DO_REGION" >/dev/null || true
    echo "<VPC_ID>"; return
  fi
  vid="$(doctl vpcs list --format ID,Name --no-header 2>/dev/null | awk -v n="$VPC_NAME" '$2==n {print $1; exit}')"
  if [ -z "$vid" ]; then
    echo "Creating VPC $VPC_NAME in $DO_REGION..." >&2
    doctl vpcs create --name "$VPC_NAME" --region "$DO_REGION" >/dev/null
    vid="$(doctl vpcs list --format ID,Name --no-header | awk -v n="$VPC_NAME" '$2==n {print $1; exit}')"
  else
    echo "Reusing VPC $VPC_NAME ($vid)" >&2
  fi
  echo "$vid"
}

# ── Create or reuse one droplet; echoes its id ──
create_droplet() {
  local name="$1" tag="$2" vpc="$3" ssh_key="$4" public="$5"
  local existing
  existing="$(droplet_id_by_name "$name")"
  if [ -n "$existing" ]; then
    assert_not_protected "$existing"
    echo "Droplet $name exists ($existing) — reusing" >&2
    echo "$existing"; return
  fi

  local args=(
    compute droplet create "$name"
    --region "$DO_REGION" --size "$DO_SIZE" --image "$IMAGE"
    --ssh-keys "$ssh_key" --tag-names "fixitlab,fixitlab-cluster,$tag"
    --enable-monitoring --enable-private-networking --wait
  )
  [ -n "$vpc" ] && [ "$vpc" != "<VPC_ID>" ] && args+=(--vpc-uuid "$vpc")
  # Edge gets the platform bootstrap as user-data; all nodes are bootstrapped
  # again later by ci-bootstrap-cluster.sh with role-specific steps.
  local bootstrap="$ROOT/infra/digitalocean/bootstrap-platform.sh"
  [ -f "$bootstrap" ] && args+=(--user-data-file "$bootstrap")

  if _is_true "$DRY_RUN"; then
    echo "DRY_RUN doctl ${args[*]}" >&2
    echo "<${name}_ID>"; return
  fi
  echo "Creating droplet $name ($tag)..." >&2
  doctl "${args[@]}" >/dev/null
  droplet_id_by_name "$name"
}

get_public_ip() {
  local id="$1"
  if _is_true "$DRY_RUN"; then echo "<PUBLIC_IP>"; return; fi
  doctl compute droplet get "$id" --format PublicIPv4 --no-header
}
get_private_ip() {
  local id="$1"
  if _is_true "$DRY_RUN"; then echo "<PRIVATE_IP>"; return; fi
  doctl compute droplet get "$id" --format PrivateIPv4 --no-header
}

wait_for_ssh() {
  local ip="$1" label="$2"
  if _is_true "$DRY_RUN"; then
    echo "DRY_RUN ssh -o StrictHostKeyChecking=no root@${ip} 'command -v docker'  # wait for $label" >&2
    return 0
  fi
  local opts=(-o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes)
  local kf=""
  if [ -n "${PROD_SSH_KEY:-}" ]; then
    kf="$(mktemp)"; printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$kf"; chmod 600 "$kf"; opts+=(-i "$kf")
  fi
  local i
  for i in $(seq 1 40); do
    if ssh "${opts[@]}" "root@${ip}" "true" >/dev/null 2>&1; then
      echo "  SSH ready on $label ($ip) attempt $i" >&2
      [ -n "$kf" ] && rm -f "$kf"; return 0
    fi
    sleep 15
  done
  [ -n "$kf" ] && rm -f "$kf"
  echo "  WARN: SSH not ready on $label ($ip) — later jobs may retry" >&2
}

main() {
  echo "=== FixitLab cluster create (region=$DO_REGION size=$DO_SIZE dry_run=$DRY_RUN wire_existing=$WIRE_EXISTING) ==="
  local ssh_key vpc edge_id app_id db_id labs_id

  if _is_true "$WIRE_EXISTING"; then
    echo "WIRE_EXISTING=1 — discovering droplets by tag (no creation)"
    vpc="$(ensure_vpc)"
    if _is_true "$DRY_RUN"; then
      echo "DRY_RUN doctl compute droplet list --tag-name fixitlab-edge|app|db|labs --format ID  # discover existing"
      edge_id="<edge_ID>"; app_id="<app_ID>"; db_id="<db_ID>"; labs_id="<labs_ID>"
    else
      edge_id="$(droplet_id_by_tag fixitlab-edge)"
      app_id="$(droplet_id_by_tag fixitlab-app)"
      db_id="$(droplet_id_by_tag fixitlab-db)"
      labs_id="$(droplet_id_by_tag fixitlab-labs)"
      for pair in "edge:$edge_id" "app:$app_id" "db:$db_id" "labs:$labs_id"; do
        if [ -z "${pair#*:}" ]; then
          echo "ERROR: no droplet found for tag fixitlab-${pair%%:*}"; exit 1
        fi
      done
    fi
  else
    ssh_key="$(resolve_ssh_key_id)"
    vpc="$(ensure_vpc)"
    edge_id="$(create_droplet "$EDGE_NAME" fixitlab-edge "$vpc" "$ssh_key" public)"
    app_id="$(create_droplet "$APP_NAME"  fixitlab-app  "$vpc" "$ssh_key" private)"
    db_id="$(create_droplet "$DB_NAME"    fixitlab-db   "$vpc" "$ssh_key" private)"
    labs_id="$(create_droplet "$LABS_NAME" fixitlab-labs "$vpc" "$ssh_key" private)"
  fi

  local edge_public edge_private app_private db_private labs_private
  edge_public="$(get_public_ip "$edge_id")"
  edge_private="$(get_private_ip "$edge_id")"
  app_private="$(get_private_ip "$app_id")"
  db_private="$(get_private_ip "$db_id")"
  labs_private="$(get_private_ip "$labs_id")"

  # Edge is the only public node we SSH to from CI; others are reached via edge
  # or their private IPs from within the VPC. Wait on public/edge here.
  wait_for_ssh "$edge_public" edge

  emit_output vpc_id "$vpc"
  emit_output edge_id "$edge_id"
  emit_output app_id "$app_id"
  emit_output db_id "$db_id"
  emit_output labs_id "$labs_id"
  emit_output edge_public_ip "$edge_public"
  emit_output edge_private_ip "$edge_private"
  emit_output app_private_ip "$app_private"
  emit_output db_private_ip "$db_private"
  emit_output labs_private_ip "$labs_private"

  echo "=== cluster create done ==="
}

main "$@"
