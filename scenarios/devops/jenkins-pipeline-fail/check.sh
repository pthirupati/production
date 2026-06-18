#!/bin/bash
# Check that Jenkinsfile has valid Groovy pipeline syntax
FAILED=0
JENKINSFILE="/var/jenkins_home/workspace/myapp/Jenkinsfile"

if [ ! -f "$JENKINSFILE" ]; then
    echo "FAIL: Jenkinsfile not found at $JENKINSFILE"
    exit 1
fi

# Must have pipeline block
if grep -q "^pipeline {" "$JENKINSFILE"; then
    echo "OK: pipeline block present"
else
    echo "FAIL: Missing top-level pipeline { block"
    FAILED=1
fi

# Must not have BROKEN marker
if grep -q "BROKEN" "$JENKINSFILE"; then
    echo "FAIL: BROKEN marker still present in Jenkinsfile"
    FAILED=1
fi

# Count braces - must be balanced
OPEN=$(grep -o '{' "$JENKINSFILE" | wc -l)
CLOSE=$(grep -o '}' "$JENKINSFILE" | wc -l)
if [ "$OPEN" -eq "$CLOSE" ]; then
    echo "OK: Braces are balanced ($OPEN open, $CLOSE close)"
else
    echo "FAIL: Unbalanced braces — $OPEN opening vs $CLOSE closing"
    FAILED=1
fi

# Must have stages block
if grep -q "stages {" "$JENKINSFILE"; then
    echo "OK: stages block present"
else
    echo "FAIL: Missing stages { block"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: Jenkinsfile syntax is fixed" && exit 0
exit 1
