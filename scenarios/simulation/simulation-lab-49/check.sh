#!/usr/bin/env bash
# Fail-closed grading — learner must apply the documented fix in the lab.
MARKER="${FIX_MARKER:-/tmp/scenario-fixed}"
if [[ -f "$MARKER" ]] && grep -q FIXED-OK "$MARKER" 2>/dev/null; then
  exit 0
fi
exit 1
