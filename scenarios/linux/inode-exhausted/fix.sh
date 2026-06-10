#!/bin/bash
set -e
find /var/cache/app -type f -delete 2>/dev/null || true
find /var/cache -type f -name '*.tmp' -delete 2>/dev/null || true
