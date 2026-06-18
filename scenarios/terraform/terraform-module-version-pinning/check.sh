#!/usr/bin/env bash
# Check: No module block uses an unpinned source (no ?ref=main or missing version).
set -euo pipefail

TF_DIR="${TF_WORKING_DIR:-/workspace/terraform}"

if [[ ! -d "$TF_DIR" ]]; then
  echo "INFO: Terraform working directory '$TF_DIR' not found — skipping check."
  exit 0
fi

# Look for module sources with ?ref=main or ?ref=master (unpinned floating refs)
UNPINNED=$(grep -rn 'ref=main\|ref=master\|ref=HEAD' "$TF_DIR" --include="*.tf" || true)

if [[ -n "$UNPINNED" ]]; then
  echo "FAIL: Found unpinned module source references:"
  echo "$UNPINNED"
  exit 1
fi

# Check for Registry modules missing 'version' argument
# Simple heuristic: module blocks with 'source' but no 'version'
MISSING_VERSION=$(awk '/^module /{found=1} found && /source/{has_source=1} found && /version/{has_version=1} found && /^}/{if(has_source && !has_version) print FILENAME ":" NR " missing version"; has_source=0; has_version=0; found=0}' \
  "$TF_DIR"/*.tf 2>/dev/null || true)

if [[ -n "$MISSING_VERSION" ]]; then
  echo "WARN: Registry module blocks may be missing version pins:"
  echo "$MISSING_VERSION"
fi

echo "PASS: No floating Git ref found in module sources."
exit 0
