#!/bin/bash
# Check that ArgoCD application manifests are fixed and sync succeeds
FAILED=0
MANIFEST_DIR="/opt/gitops/myapp/manifests"
DEPLOYMENT="$MANIFEST_DIR/deployment.yaml"

if [ ! -d "$MANIFEST_DIR" ]; then
    echo "FAIL: Manifest directory not found at $MANIFEST_DIR"
    exit 1
fi

# Check deployment manifest exists
if [ ! -f "$DEPLOYMENT" ]; then
    echo "FAIL: deployment.yaml not found"
    FAILED=1
fi

# Check invalid cpu limit '0' is gone
if grep -q "cpu: \"0\"" "$DEPLOYMENT" 2>/dev/null || grep -q "cpu: '0'" "$DEPLOYMENT" 2>/dev/null; then
    echo "FAIL: Invalid cpu limit '0' still present in deployment.yaml"
    FAILED=1
else
    echo "OK: Invalid cpu limit '0' has been removed"
fi

# Check a valid cpu limit is set
if grep -qE "cpu: ['\"]?[0-9]+m['\"]?" "$DEPLOYMENT" 2>/dev/null; then
    CPU=$(grep -oE "cpu: ['\"]?[0-9]+m['\"]?" "$DEPLOYMENT" | head -1)
    echo "OK: Valid CPU limit set: $CPU"
else
    echo "FAIL: No valid CPU limit (e.g. 500m) found in deployment.yaml"
    FAILED=1
fi

# Validate manifest with kubectl dry-run if available
if command -v kubectl > /dev/null 2>&1; then
    if kubectl apply --dry-run=client -f "$MANIFEST_DIR" > /dev/null 2>&1; then
        echo "OK: Manifests pass kubectl dry-run validation"
    else
        echo "FAIL: Manifests still fail kubectl dry-run validation"
        FAILED=1
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: ArgoCD manifests fixed — sync should succeed" && exit 0
exit 1
