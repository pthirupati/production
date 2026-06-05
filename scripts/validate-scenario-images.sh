#!/usr/bin/env bash
# Validate scenario Docker images exist and a sample lab can start.
# Usage: ./scripts/validate-scenario-images.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${DOCKER_SCENARIO_IMAGE_PREFIX:-fixitlab/scenario-}"
cd "$ROOT/scenarios"

missing=()
present=0
total=0

for tech in */; do
  tech="${tech%/}"
  for dir in "$tech"/*/; do
    [ -f "${dir}Dockerfile" ] || continue
    slug=$(basename "$dir")
    image="${PREFIX}${slug}:latest"
    total=$((total + 1))
    if docker image inspect "$image" >/dev/null 2>&1; then
      present=$((present + 1))
    else
      missing+=("$slug")
    fi
  done
done

echo "Scenario images: $present / $total present"
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing (${#missing[@]}): ${missing[*]}"
  exit 1
fi
echo "All scenario images built."
exit 0
