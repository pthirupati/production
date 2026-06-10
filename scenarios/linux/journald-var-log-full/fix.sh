#!/bin/bash
set -e
journalctl --vacuum-size=50M 2>/dev/null || true
rm -f /var/log/big/*.log 2>/dev/null || true
