#!/bin/bash
# Check that the cached DNS entry has been flushed and correct IP is returned
RESOLVED=$(dig @localhost app.internal +short 2>/dev/null | head -1)
if [ "$RESOLVED" = "10.0.1.50" ]; then
  echo "OK: app.internal resolves to correct IP 10.0.1.50"
  exit 0
fi
if [ "$RESOLVED" = "10.66.66.66" ]; then
  echo "FAIL: app.internal still resolves to poisoned IP 10.66.66.66 — flush cache with: rndc flushname app.internal"
  exit 1
fi
# Fallback: check if rndc flush was run by looking at cache size
if rndc stats 2>/dev/null && grep -q 'cache hits' /var/named/data/named_stats.txt 2>/dev/null; then
  echo "FAIL: cache flush confirmed but app.internal still not resolving correctly"
  exit 1
fi
echo "FAIL: cannot verify DNS resolution for app.internal — ensure named is running and cache is flushed"
exit 1
