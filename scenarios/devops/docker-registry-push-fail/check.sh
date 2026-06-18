#!/bin/bash
# Check that Docker is configured for private registry pushes
FAILED=0
DAEMON_JSON="/etc/docker/daemon.json"

if [ ! -f "$DAEMON_JSON" ]; then
    echo "FAIL: /etc/docker/daemon.json not found"
    exit 1
fi

# Check insecure-registries is configured
if python3 -c "import json; d=json.load(open('$DAEMON_JSON')); exit(0 if 'registry.internal:5000' in d.get('insecure-registries', []) else 1)" 2>/dev/null; then
    echo "OK: registry.internal:5000 in insecure-registries"
elif grep -q 'registry.internal:5000' "$DAEMON_JSON"; then
    echo "OK: registry.internal:5000 found in daemon.json"
else
    echo "FAIL: registry.internal:5000 not in insecure-registries in daemon.json"
    FAILED=1
fi

# Check Docker config has credentials stored
DOCKER_CONFIG="${HOME}/.docker/config.json"
if [ -f "$DOCKER_CONFIG" ] && grep -q 'registry.internal:5000' "$DOCKER_CONFIG"; then
    echo "OK: Docker credentials configured for registry.internal:5000"
else
    echo "FAIL: Docker credentials for registry.internal:5000 not found in $DOCKER_CONFIG"
    FAILED=1
fi

# Check Docker daemon is running
if systemctl is-active docker > /dev/null 2>&1; then
    echo "OK: Docker daemon is running"
else
    echo "FAIL: Docker daemon is not running — restart needed after config change"
    FAILED=1
fi

# Validate daemon.json is valid JSON
if python3 -m json.tool "$DAEMON_JSON" > /dev/null 2>&1; then
    echo "OK: daemon.json is valid JSON"
else
    echo "FAIL: daemon.json is not valid JSON"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: Docker registry push config has been fixed" && exit 0
exit 1
