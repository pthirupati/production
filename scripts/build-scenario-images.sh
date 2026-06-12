#!/usr/bin/env bash
# Build all scenario Docker images locally (run on platform server after deploy)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHARED="$ROOT/scenarios/shared"
PREFIX="${DOCKER_SCENARIO_IMAGE_PREFIX:-fixitlab/scenario-}"
cd "$ROOT/scenarios"

LOOP_SLUGS="lvm-extend lvm-add-pv-extend lvm-pvmove-evacuate mdadm-degraded-array fstab-bad-uuid fs-readonly-remount"
DNS_SLUGS="resolv-dead-nameserver dns-resolution-broken"

needs_helper() {
  local slug="$1"
  local list="$2"
  [[ " $list " == *" $slug "* ]]
}

stage_shared_helpers() {
  local dir="$1"
  local slug="$2"
  cp "$SHARED/systemctl.py" "$SHARED/service.sh" "$dir/" 2>/dev/null || true
  if needs_helper "$slug" "$LOOP_SLUGS"; then
    cp "$SHARED/lab-loop.sh" "$dir/"
    chmod +x "$dir/lab-loop.sh"
  fi
  if needs_helper "$slug" "$DNS_SLUGS"; then
    cp "$SHARED/lab-dnsmasq.sh" "$dir/"
    chmod +x "$dir/lab-dnsmasq.sh"
  fi
}

built=0
failed=0
failed_list=()

for tech in */; do
  tech="${tech%/}"
  for dir in "$tech"/*/; do
    [ -f "${dir}Dockerfile" ] || continue
    slug=$(basename "$dir")
    image="${PREFIX}${slug}:latest"
    stage_shared_helpers "$dir" "$slug"
    echo "==> Building $image"
    if docker build -t "$image" "$dir"; then
      built=$((built + 1))
    else
      failed=$((failed + 1))
      failed_list+=("$slug")
      echo "!! FAILED: $image"
    fi
  done
done

echo "Built $built scenario images."
if [ "$failed" -gt 0 ]; then
  echo "Failed $failed: ${failed_list[*]}"
  exit 1
fi
