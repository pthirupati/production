#!/bin/bash
set -e
id deploy >/dev/null 2>&1 && usermod -s /bin/bash deploy || true
