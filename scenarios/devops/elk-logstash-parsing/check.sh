#!/bin/bash
# Check that Logstash grok pattern has been fixed
FAILED=0
LOGSTASH_CONF="/etc/logstash/conf.d/app.conf"

if [ ! -f "$LOGSTASH_CONF" ]; then
    echo "FAIL: Logstash config not found at $LOGSTASH_CONF"
    exit 1
fi

# Check the old broken pattern (without brackets) is replaced
if grep -q 'TIMESTAMP_ISO8601:timestamp}[^]\\]' "$LOGSTASH_CONF"; then
    # Pattern without leading bracket escape
    if ! grep -q '\\[%{TIMESTAMP_ISO8601' "$LOGSTASH_CONF"; then
        echo "FAIL: Grok pattern missing bracket escape for timestamp — should start with \\["
        FAILED=1
    fi
fi

# Check the pattern includes bracket escapes for the timestamp
if grep -q '\\\[%{TIMESTAMP_ISO8601' "$LOGSTASH_CONF" || grep -q '\\[%{TIMESTAMP_ISO8601' "$LOGSTASH_CONF"; then
    echo "OK: Grok pattern includes bracket escape for timestamp format"
else
    echo "FAIL: Grok pattern does not escape brackets around timestamp"
    FAILED=1
fi

# Check LOGLEVEL pattern is used
if grep -q 'LOGLEVEL' "$LOGSTASH_CONF"; then
    echo "OK: LOGLEVEL pattern present in grok filter"
else
    echo "FAIL: LOGLEVEL pattern not found in grok filter"
    FAILED=1
fi

# Check GREEDYDATA for message field
if grep -q 'GREEDYDATA:message' "$LOGSTASH_CONF"; then
    echo "OK: GREEDYDATA:message pattern present"
else
    echo "FAIL: GREEDYDATA:message not found in grok pattern"
    FAILED=1
fi

# Validate Logstash config syntax if available
if command -v logstash > /dev/null 2>&1; then
    if logstash --config.test_and_exit -f "$LOGSTASH_CONF" > /dev/null 2>&1; then
        echo "OK: Logstash config syntax is valid"
    else
        echo "FAIL: Logstash config has syntax errors"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Logstash grok pattern has been fixed" && exit 0
exit 1
