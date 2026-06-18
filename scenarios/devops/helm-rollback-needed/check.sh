#!/bin/bash
# Check that Helm release has been rolled back successfully
FAILED=0
NAMESPACE="production"
RELEASE="myapp"

# Check helm history shows a rollback
if command -v helm > /dev/null 2>&1; then
    HISTORY=$(helm history "$RELEASE" -n "$NAMESPACE" 2>/dev/null)
    if echo "$HISTORY" | grep -qi "rollback"; then
        echo "OK: Helm history shows a rollback was performed"
    else
        echo "FAIL: No rollback found in helm history for $RELEASE"
        FAILED=1
    fi

    # Check current deployed revision
    CURRENT=$(helm status "$RELEASE" -n "$NAMESPACE" 2>/dev/null | grep "REVISION:")
    echo "INFO: $CURRENT"

    # Check status is deployed
    if helm status "$RELEASE" -n "$NAMESPACE" 2>/dev/null | grep -q "STATUS: deployed"; then
        echo "OK: Helm release is in deployed state"
    else
        echo "FAIL: Helm release is not in deployed state"
        FAILED=1
    fi
fi

# Check pods are running
if command -v kubectl > /dev/null 2>&1; then
    CRASHLOOP=$(kubectl get pods -n "$NAMESPACE" 2>/dev/null | grep -c "ImagePullBackOff\|CrashLoopBackOff")
    if [ "$CRASHLOOP" -eq 0 ]; then
        echo "OK: No pods in ImagePullBackOff or CrashLoopBackOff"
    else
        echo "FAIL: $CRASHLOOP pod(s) still in error state after rollback"
        FAILED=1
    fi

    RUNNING=$(kubectl get pods -n "$NAMESPACE" 2>/dev/null | grep -c "Running")
    echo "INFO: $RUNNING pod(s) running in $NAMESPACE namespace"
fi

[ $FAILED -eq 0 ] && echo "PASS: Helm rollback completed successfully" && exit 0
exit 1
