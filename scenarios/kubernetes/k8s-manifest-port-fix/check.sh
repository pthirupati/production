#!/bin/bash
# Validation: k8s manifest port alignment + nginx running
FAILED=0
MANIFEST="/opt/k8s/deployment.yaml"

if [ ! -f "$MANIFEST" ]; then
    echo "FAIL: deployment.yaml not found"
    exit 1
fi

# Service targetPort must match containerPort (80)
if grep -q 'targetPort: 8080' "$MANIFEST"; then
    echo "FAIL: Service targetPort is still 8080 but container listens on port 80"
    FAILED=1
else
    echo "OK: Service targetPort aligned with container"
fi

if grep -q 'containerPort: 80' "$MANIFEST"; then
    echo "OK: containerPort is 80"
else
    echo "FAIL: containerPort should be 80"
    FAILED=1
fi

if pgrep nginx >/dev/null 2>&1 || curl -sf http://127.0.0.1/ >/dev/null 2>&1; then
    echo "OK: Web server is responding"
else
    echo "FAIL: Nginx/web server is not running — start it with `service nginx start`"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: Kubernetes deployment config fixed" && exit 0
exit 1
