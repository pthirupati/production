#!/usr/bin/env bash
# FixitLab — DOKS (DigitalOcean Kubernetes) provisioning STUB.
#
# SCAFFOLD: by default PRINTS what it WOULD do and exits 0. It only creates a
# managed cluster when a DO token is present AND APPLY=1 is set explicitly. The
# default four-droplet pipeline never calls this script.
#
# A DO token is usually already available to the platform (DO_API_TOKEN or inside
# PRODUCTION_ENV_B64), but creating a managed cluster is a deliberate, paid action
# — hence the explicit APPLY=1 gate on top of token presence.
#
# Usage (scaffold / dry):   bash infra/k8s/provision-doks.sh
# Usage (real, gated):      APPLY=1 bash infra/k8s/provision-doks.sh
set -euo pipefail

APPLY="${APPLY:-0}"
DOKS_NAME="${DOKS_NAME:-fixitlab-doks}"
DO_REGION="${DO_REGION:-blr1}"
DOKS_VERSION="${DOKS_VERSION:-latest}"
NODE_SIZE="${DOKS_NODE_SIZE:-s-4vcpu-8gb}"
NODE_MIN="${DOKS_NODE_MIN:-3}"
NODE_MAX="${DOKS_NODE_MAX:-20}"

_is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

# Resolve a DO token without echoing it.
TOKEN="${DO_API_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -n "${PRODUCTION_ENV_B64:-}" ]; then
  TOKEN="$(echo "$PRODUCTION_ENV_B64" | base64 -d | grep '^DO_API_TOKEN=' | cut -d= -f2- | tr -d '\r' || true)"
fi
[ -n "$TOKEN" ] && [ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::$TOKEN"

echo "=== FixitLab DOKS provisioning (SCAFFOLD) ==="
echo "  name=${DOKS_NAME}  region=${DO_REGION}  node_size=${NODE_SIZE}  nodes=${NODE_MIN}-${NODE_MAX}  apply=${APPLY}"

if [ -z "$TOKEN" ]; then
  echo "::notice::No DO token detected — SCAFFOLD no-op."
  echo "Would, once a DO token exists:"
  echo "  1. doctl kubernetes cluster create ${DOKS_NAME} (region ${DO_REGION}, autoscaling ${NODE_MIN}-${NODE_MAX} x ${NODE_SIZE})."
  echo "  2. Save kubeconfig, install ingress-nginx + cert-manager via Helm."
  echo "  3. Point ConfigMap hosts at DO Managed PostgreSQL + Managed Redis."
  echo "  4. kubectl apply -k infra/k8s/overlays/doks (images from Docker Hub)."
  echo "Set DO_API_TOKEN + APPLY=1 to run for real. See docs/KUBERNETES.md."
  exit 0
fi

echo "DO token detected."
if ! _is_true "$APPLY"; then
  echo "APPLY not set — refusing to create a (paid) managed cluster. Re-run with APPLY=1."
  exit 0
fi

command -v doctl >/dev/null 2>&1 || { echo "ERROR: doctl not installed"; exit 1; }
doctl auth init -t "$TOKEN" >/dev/null 2>&1 || true

if doctl kubernetes cluster get "$DOKS_NAME" >/dev/null 2>&1; then
  echo "Cluster $DOKS_NAME already exists — reusing."
else
  echo "Creating DOKS cluster $DOKS_NAME ..."
  doctl kubernetes cluster create "$DOKS_NAME" \
    --region "$DO_REGION" \
    --version "$DOKS_VERSION" \
    --node-pool "name=app;size=${NODE_SIZE};auto-scale=true;min-nodes=${NODE_MIN};max-nodes=${NODE_MAX}" \
    --wait
fi
doctl kubernetes cluster kubeconfig save "$DOKS_NAME"
echo "=== DOKS provisioning done — kubeconfig saved ==="
