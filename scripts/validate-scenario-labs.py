#!/usr/bin/env python3
"""
Backward-compatible entrypoint — delegates to dynamic all-scenarios E2E.

  python /scripts/validate-scenario-labs.py

Env:
  E2E_SKIP_LAB=1  — only check images exist
  LAB_SAMPLE=N    — ignored (all deployable scenarios always tested)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

if __name__ == "__main__":
    if os.environ.get("E2E_SKIP_LAB", "0") == "1":
        from e2e_dynamic_catalog import discover_catalog
        c = discover_catalog()
        print(f"Images: {len(c['deployable'])}/{len(c['scenarios'])} present")
        if c["missing_images"]:
            print(f"Missing: {', '.join(c['missing_images'][:20])}")
            sys.exit(1)
        sys.exit(0)

    from e2e_all_scenarios_labs import main, cleanup
    code = 1
    try:
        code = main()
    finally:
        if os.environ.get("E2E_SKIP_CLEANUP", "0") != "1":
            cleanup()
    sys.exit(code)
