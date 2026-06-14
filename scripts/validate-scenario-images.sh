#!/usr/bin/env bash
# Validate scenario Docker images exist for non-simulation labs.
# Simulation scenarios (lab_mode: simulation) do not require local Docker images.
# Usage: ./scripts/validate-scenario-images.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PREFIX="${DOCKER_SCENARIO_IMAGE_PREFIX:-fixitlab/scenario-}"
cd "$ROOT/scenarios"

is_simulation_scenario() {
  local dir="$1"
  local yaml=""
  if [ -f "${dir}scenario.yaml" ]; then
    yaml="${dir}scenario.yaml"
  elif [ -f "${dir}meta.yaml" ]; then
    yaml="${dir}meta.yaml"
  else
    return 1
  fi
  grep -qE '^lab_mode:\s*simulation\s*$' "$yaml" 2>/dev/null
}

missing=()
present=0
total=0
skipped_sim=0

for tech in */; do
  tech="${tech%/}"
  for dir in "$tech"/*/; do
    [ -f "${dir}Dockerfile" ] || continue
    if is_simulation_scenario "$dir"; then
      skipped_sim=$((skipped_sim + 1))
      continue
    fi
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

echo "Scenario images: $present / $total present (skipped $skipped_sim simulation scenarios)"
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing (${#missing[@]}): ${missing[*]}"
  exit 1
fi
echo "All required scenario images built."
exit 0
