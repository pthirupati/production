#!/bin/bash
set -e
sed -i '/^appuser$/d' /etc/cron.deny 2>/dev/null || true
grep -q '^appuser$' /etc/cron.allow 2>/dev/null || echo 'appuser' >> /etc/cron.allow
