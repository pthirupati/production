#!/bin/bash
# Check that Jenkins JVM heap has been increased
FAILED=0
JENKINS_CONFIG="/etc/default/jenkins"

if [ ! -f "$JENKINS_CONFIG" ]; then
    echo "FAIL: Jenkins config not found at $JENKINS_CONFIG"
    exit 1
fi

# Check that old small heap setting is gone
if grep -q '\-Xmx512m' "$JENKINS_CONFIG"; then
    echo "FAIL: Old -Xmx512m setting still present — heap not increased"
    FAILED=1
fi

# Check that a larger heap is set (2g, 3g, 4g, or numeric like 2048m)
if grep -qE '\-Xmx([2-9]g|[0-9]{4,}m)' "$JENKINS_CONFIG"; then
    HEAP=$(grep -oE '\-Xmx[0-9]+[gGmM]' "$JENKINS_CONFIG" | head -1)
    echo "OK: Heap setting found: $HEAP"
else
    echo "FAIL: JVM heap not set to at least 2g in JAVA_ARGS"
    FAILED=1
fi

# Check JAVA_ARGS line exists
if grep -q 'JAVA_ARGS' "$JENKINS_CONFIG"; then
    echo "OK: JAVA_ARGS configured"
else
    echo "FAIL: JAVA_ARGS not found in Jenkins config"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: Jenkins JVM heap settings updated" && exit 0
exit 1
