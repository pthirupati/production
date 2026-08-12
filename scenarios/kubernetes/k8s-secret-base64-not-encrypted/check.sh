#!/usr/bin/env bash
# k8s-secret-base64-not-encrypted: fail-CLOSED encryption-at-rest check.
#
# Graded for real by apps.vmware_sim.k8s_engine.validate_k8s_lab
# (require_secret_encrypted_at_rest); this script mirrors that contract for
# non-simulation runs.
#
# It deliberately NEVER inspects the Secret's `data:` encoding. The whole point
# of the lab is that re-running `base64` on the value changes nothing about how
# etcd stores it, so an encoding check would pass the exact learner the lab is
# meant to correct. Only structural evidence counts.
set -uo pipefail

NS=production
SECRET=db-credentials

# Path B — value moved out of etcd behind an External Secrets Operator object.
# The ExternalSecret must actually reference a store; a bare object proves nothing.
if kubectl get externalsecret -n "$NS" -o json 2>/dev/null \
    | grep -q '"secretStoreRef"'; then
  if kubectl get externalsecret -n "$NS" -o json 2>/dev/null \
      | grep -q "\"$SECRET\""; then
    echo "PASS: $NS/$SECRET is sourced from an external secret store"
    exit 0
  fi
fi

# Path A — encryption at rest on the API server.
ENC_FILE=$(grep -ho -- '--encryption-provider-config=[^[:space:]"]*' \
  /etc/kubernetes/manifests/kube-apiserver.yaml 2>/dev/null | head -1 | cut -d= -f2-)

if [ -z "$ENC_FILE" ] || [ ! -r "$ENC_FILE" ]; then
  echo "FAIL: no readable --encryption-provider-config on kube-apiserver; Secrets use the identity provider"
  exit 1
fi

# The config must cover the secrets resource.
if ! grep -qE '^[[:space:]]*-[[:space:]]*secrets[[:space:]]*$' "$ENC_FILE"; then
  echo "FAIL: EncryptionConfiguration does not cover the 'secrets' resource"
  exit 1
fi

# The first provider decides what gets written. `identity` is the no-op provider,
# so a config that lists it first encrypts nothing even though it looks configured.
FIRST_PROVIDER=$(grep -oE '^[[:space:]]+-[[:space:]]*(identity|aescbc|aesgcm|secretbox|kms):' "$ENC_FILE" \
  | head -1 | tr -d ' -:')
case "$FIRST_PROVIDER" in
  aescbc|aesgcm|secretbox|kms) ;;
  identity)
    echo "FAIL: 'identity' is listed first — writes are still plaintext"
    exit 1
    ;;
  *)
    echo "FAIL: no recognised encryption provider in $ENC_FILE"
    exit 1
    ;;
esac

# Enabling a provider only affects writes made after the restart. A Secret that
# predates the config sits in etcd in plaintext until something rewrites it, so
# require the stored bytes to actually be ciphertext.
STORED=$(ETCDCTL_API=3 etcdctl --endpoints=127.0.0.1:2379 \
  get "/registry/secrets/$NS/$SECRET" 2>/dev/null | head -c 4096)
if [ -z "$STORED" ]; then
  echo "FAIL: cannot read $NS/$SECRET from etcd to confirm it was rewritten"
  exit 1
fi
if ! printf '%s' "$STORED" | grep -q "k8s:enc:$FIRST_PROVIDER"; then
  echo "FAIL: $NS/$SECRET predates the encryption config and is still stored in plaintext; rewrite existing Secrets"
  exit 1
fi

echo "PASS: $NS/$SECRET is encrypted at rest with the $FIRST_PROVIDER provider"
exit 0
