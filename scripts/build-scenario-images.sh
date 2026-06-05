#!/usr/bin/env bash
# Build all scenario Docker images locally (run on platform server after deploy)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${DOCKER_SCENARIO_IMAGE_PREFIX:-fixitlab/scenario-}"
cd "$ROOT/scenarios"

built=0
failed=0
failed_list=()

for tech in */; do
  tech="${tech%/}"
  for dir in "$tech"/*/; do
    [ -f "${dir}Dockerfile" ] || continue
    slug=$(basename "$dir")
    image="${PREFIX}${slug}:latest"
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
