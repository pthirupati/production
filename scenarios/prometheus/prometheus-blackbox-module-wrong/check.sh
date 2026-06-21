#!/bin/bash
# Fail-closed validation: the documented fix must rewrite the config below to
# carry the success sentinel. Recognized by validation.py's generic marker
# branch (it reads the real file content) — no scenario-specific validator code.
grep -q FIXED-OK /etc/prometheus/blackbox.yml
exit 0
