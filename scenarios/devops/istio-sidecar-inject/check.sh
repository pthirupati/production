#!/bin/bash
# Check that Istio sidecar injection is enabled for the myapp namespace
FAILED=0
NAMESPACE="myapp"

if ! command -v kubectl > /dev/null 2>&1; then
    echo "FAIL: kubectl not found"
    exit 1
fi

# Check namespace has istio-injection=enabled label
NS_LABELS=$(kubectl get namespace "$NAMESPACE" --show-labels 2>/dev/null)
if echo "$NS_LABELS" | grep -q 'istio-injection=enabled'; then
    echo "OK: istio-injection=enabled label present on namespace $NAMESPACE"
else
    echo "FAIL: Namespace $NAMESPACE does not have istio-injection=enabled label"
    FAILED=1
fi

# Check that the disabled label is gone
if echo "$NS_LABELS" | grep -q 'istio-injection=disabled'; then
    echo "FAIL: istio-injection=disabled label still present — overwrite needed"
    FAILED=1
fi

# Check that running pods have the istio-proxy sidecar
PODS_WITH_SIDECAR=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[*].spec.containers[*].name}' 2>/dev/null | tr ' ' '\n' | grep -c 'istio-proxy')
TOTAL_PODS=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l)

if [ "$TOTAL_PODS" -gt 0 ]; then
    if [ "$PODS_WITH_SIDECAR" -gt 0 ]; then
        echo "OK: $PODS_WITH_SIDECAR pod(s) have istio-proxy sidecar running"
    else
        echo "FAIL: No pods have istio-proxy sidecar — restart deployments needed"
        FAILED=1
    fi
else
    echo "INFO: No pods running in $NAMESPACE namespace yet"
fi

[ $FAILED -eq 0 ] && echo "PASS: Istio sidecar injection is enabled and active" && exit 0
exit 1
