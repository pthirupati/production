#!/usr/bin/env bash
# Read a single KEY=value from an env file without sourcing (handles spaces in values).
env_val() {
  local key="$1" file="$2"
  [ -f "$file" ] || return 0
  grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- || true
}
