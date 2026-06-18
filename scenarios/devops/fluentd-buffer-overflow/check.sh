#!/bin/bash
# Check that Fluentd buffer settings have been tuned
FAILED=0
FLUENT_CONF="/etc/fluent/fluent.conf"

if [ ! -f "$FLUENT_CONF" ]; then
    echo "FAIL: Fluentd config not found at $FLUENT_CONF"
    exit 1
fi

# Check old small chunk_limit_size 1m is gone
if grep -q 'chunk_limit_size\s*1m$\|chunk_limit_size\s*1M$' "$FLUENT_CONF"; then
    echo "FAIL: Old chunk_limit_size 1m still present — needs to be increased"
    FAILED=1
else
    echo "OK: Old 1m chunk_limit_size removed"
fi

# Check chunk_limit_size is at least 8m
if grep -qE 'chunk_limit_size\s+[8-9][0-9]*m|chunk_limit_size\s+[1-9][0-9]+m' "$FLUENT_CONF"; then
    CHUNK=$(grep -oE 'chunk_limit_size\s+[0-9]+[mMgG]' "$FLUENT_CONF" | head -1)
    echo "OK: Buffer chunk_limit_size set: $CHUNK"
else
    echo "FAIL: chunk_limit_size not increased to at least 8m"
    FAILED=1
fi

# Check total_limit_size is at least 256m
if grep -qE 'total_limit_size\s+([0-9]{3,}m|[1-9][gG])' "$FLUENT_CONF"; then
    TOTAL=$(grep -oE 'total_limit_size\s+[0-9]+[mMgG]' "$FLUENT_CONF" | head -1)
    echo "OK: Buffer total_limit_size set: $TOTAL"
else
    echo "FAIL: total_limit_size not increased to at least 256m"
    FAILED=1
fi

# Validate Fluentd config syntax
if command -v fluentd > /dev/null 2>&1; then
    if fluentd --dry-run -c "$FLUENT_CONF" > /dev/null 2>&1; then
        echo "OK: Fluentd config syntax is valid"
    else
        echo "FAIL: Fluentd config has syntax errors"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Fluentd buffer settings tuned to prevent overflow" && exit 0
exit 1
