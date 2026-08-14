#!/usr/bin/env bash
# Ensure coding-grader sandbox base images exist on the labs Docker engine (D4).
# Fail-closed: exit 1 if either image is missing after pull attempts.
#
# Usage:
#   DOCKER_HOST=ssh://root@<LABS_IP> ./scripts/ensure-sandbox-images.sh
#   ALLOW_MISSING_SANDBOX_IMAGES=1  # ops escape hatch (exit 0 with WARN)
set -euo pipefail

PY_IMG="${SANDBOX_PYTHON_IMAGE:-python:3.12-alpine}"
NODE_IMG="${SANDBOX_NODE_IMAGE:-node:20-alpine}"
ALLOW_MISSING="${ALLOW_MISSING_SANDBOX_IMAGES:-0}"

echo "[sandbox-images] DOCKER_HOST=${DOCKER_HOST:-<default local>} pulling ${PY_IMG} ${NODE_IMG}"

pull_one() {
  local img="$1"
  if timeout 120 docker pull "$img"; then
    echo "  pulled $img"
  else
    echo "  WARN: pull failed for $img"
  fi
}

pull_one "$PY_IMG"
pull_one "$NODE_IMG"

missing=()
for img in "$PY_IMG" "$NODE_IMG"; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    missing+=("$img")
  fi
done

if [ "${#missing[@]}" -eq 0 ]; then
  echo "[sandbox-images] OK — both grader images present"
  exit 0
fi

echo "[sandbox-images] MISSING: ${missing[*]}"
if [ "$ALLOW_MISSING" = "1" ]; then
  echo "[sandbox-images] ALLOW_MISSING_SANDBOX_IMAGES=1 — continuing"
  exit 0
fi
exit 1
