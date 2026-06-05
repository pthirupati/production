#!/usr/bin/env bash
# Build all scenario Docker images locally (run on platform server after deploy)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${DOCKER_SCENARIO_IMAGE_PREFIX:-fixitlab/scenario-}"
cd "$ROOT/scenarios"

built=0
for tech in */; do
  tech="${tech%/}"
  for dir in "$tech"/*/; do
    [ -f "${dir}Dockerfile" ] || continue
    slug=$(basename "$dir")
    image="${PREFIX}${slug}:latest"
    echo "==> Building $image"
    docker build -t "$image" "$dir"
    built=$((built + 1))
  done
done
echo "Built $built scenario images."
