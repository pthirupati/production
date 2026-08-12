#!/usr/bin/env bash
# Thin wrapper — keep one scanner implementation at repo-root scripts/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "$ROOT/scripts/check-no-secrets-in-git.sh" "$@"
