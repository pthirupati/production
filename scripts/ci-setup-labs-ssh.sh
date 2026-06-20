#!/usr/bin/env bash
# Provision an ed25519 SSH key so the D2 App droplet can drive the D4 Labs
# droplet's Docker engine over ssh:// (DOCKER_HOST=ssh://root@<D4>).
#
#   1. Generate a dedicated ed25519 keypair (no passphrase) in a temp dir.
#   2. Install the PRIVATE key + known_hosts on D2 at /opt/fixitlab/deploy/labs_ssh/
#      (mounted into backend/celery as /root/.ssh — see docker-compose.app.yml).
#   3. Append the PUBLIC key to D4 root's authorized_keys.
#
# The keypair is ephemeral to this run; only the installed copies persist.
# Idempotent: re-running replaces the key material on both nodes consistently.
# Never prints the private key. DRY_RUN=1 prints the ssh/keygen commands.
#
# Required env: EDGE_PUBLIC_IP APP_PRIVATE_IP LABS_PRIVATE_IP PROD_SSH_KEY
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
EDGE_PUBLIC_IP="${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP required}"
APP_PRIVATE_IP="${APP_PRIVATE_IP:?APP_PRIVATE_IP required}"
LABS_PRIVATE_IP="${LABS_PRIVATE_IP:?LABS_PRIVATE_IP required}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

KEY_FILE=""
WORKDIR=""
cleanup() { [ -n "$KEY_FILE" ] && rm -f "$KEY_FILE"; [ -n "$WORKDIR" ] && rm -rf "$WORKDIR"; }
trap cleanup EXIT

if [ -n "${PROD_SSH_KEY:-}" ] && ! _is_true "$DRY_RUN"; then
  KEY_FILE="$(mktemp)"; printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$KEY_FILE"; chmod 600 "$KEY_FILE"
fi

remote() {
  local target_ip="$1" via_edge="$2"; shift 2
  local opts=(-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes)
  [ -n "$KEY_FILE" ] && opts+=(-i "$KEY_FILE")
  [ "$via_edge" = "via-edge" ] && opts+=(-o "ProxyJump=root@${EDGE_PUBLIC_IP}")
  if _is_true "$DRY_RUN"; then
    local hop=""; [ "$via_edge" = "via-edge" ] && hop=" -J root@${EDGE_PUBLIC_IP}"
    echo "DRY_RUN ssh${hop} root@${target_ip} '$*'"
    return 0
  fi
  ssh "${opts[@]}" "root@${target_ip}" "$@"
}

echo "=== FixitLab labs SSH (D2 -> D4 remote docker) (dry_run=$DRY_RUN) ==="

if _is_true "$DRY_RUN"; then
  echo "DRY_RUN ssh-keygen -t ed25519 -N '' -C 'fixitlab-labs' -f <tmp>/labs_ed25519"
  remote "$LABS_PRIVATE_IP" via-edge "install -m 700 -d /root/.ssh && echo '<PUBKEY>' >> /root/.ssh/authorized_keys"
  remote "$APP_PRIVATE_IP" via-edge "install -m 700 -d /opt/fixitlab/deploy/labs_ssh"
  echo "DRY_RUN scp <tmp>/labs_ed25519 root@${APP_PRIVATE_IP}:/opt/fixitlab/deploy/labs_ssh/id_ed25519  (via edge)"
  remote "$APP_PRIVATE_IP" via-edge "ssh-keyscan -H ${LABS_PRIVATE_IP} >> /opt/fixitlab/deploy/labs_ssh/known_hosts"
  echo "DRY_RUN would verify: DOCKER_HOST=ssh://root@${LABS_PRIVATE_IP} docker version"
  echo "=== labs SSH (dry-run) done ==="
  exit 0
fi

WORKDIR="$(mktemp -d)"
ssh-keygen -t ed25519 -N "" -C "fixitlab-labs" -f "$WORKDIR/labs_ed25519" >/dev/null
PUBKEY="$(cat "$WORKDIR/labs_ed25519.pub")"

# Authorize the public key on D4 (remove any prior fixitlab-labs key first)
remote "$LABS_PRIVATE_IP" via-edge "install -m 700 -d /root/.ssh; \
  touch /root/.ssh/authorized_keys; chmod 600 /root/.ssh/authorized_keys; \
  grep -v 'fixitlab-labs' /root/.ssh/authorized_keys > /root/.ssh/authorized_keys.tmp 2>/dev/null || true; \
  mv /root/.ssh/authorized_keys.tmp /root/.ssh/authorized_keys 2>/dev/null || true; \
  printf '%s\n' '$PUBKEY' >> /root/.ssh/authorized_keys"

# Install the private key + known_hosts on D2 (mounted into containers as /root/.ssh)
remote "$APP_PRIVATE_IP" via-edge "install -m 700 -d /opt/fixitlab/deploy/labs_ssh"
# Copy the private key over the edge proxy without printing it.
scp -o StrictHostKeyChecking=no -o BatchMode=yes \
  ${KEY_FILE:+-i "$KEY_FILE"} \
  -o "ProxyJump=root@${EDGE_PUBLIC_IP}" \
  "$WORKDIR/labs_ed25519" "root@${APP_PRIVATE_IP}:/opt/fixitlab/deploy/labs_ssh/id_ed25519"
remote "$APP_PRIVATE_IP" via-edge "chmod 600 /opt/fixitlab/deploy/labs_ssh/id_ed25519; \
  ssh-keyscan -H ${LABS_PRIVATE_IP} > /opt/fixitlab/deploy/labs_ssh/known_hosts 2>/dev/null; \
  chmod 644 /opt/fixitlab/deploy/labs_ssh/known_hosts"

# Verify remote docker reachability from D2
if remote "$APP_PRIVATE_IP" via-edge \
  "DOCKER_HOST=ssh://root@${LABS_PRIVATE_IP} GIT_SSH_COMMAND='ssh -i /opt/fixitlab/deploy/labs_ssh/id_ed25519' \
   ssh -i /opt/fixitlab/deploy/labs_ssh/id_ed25519 -o StrictHostKeyChecking=no root@${LABS_PRIVATE_IP} 'docker version --format {{.Server.Version}}'"; then
  echo "  Remote docker engine on D4 reachable from D2"
else
  echo "  WARN: could not verify remote docker on D4 yet (deploy may retry)"
fi

echo "=== labs SSH done ==="
