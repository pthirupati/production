#!/bin/bash
# Check that SonarQube coverage path has been fixed
FAILED=0
SONAR_PROPS="/opt/app/sonar-project.properties"
CORRECT_COVERAGE="/opt/app/reports/coverage.xml"

if [ ! -f "$SONAR_PROPS" ]; then
    echo "FAIL: sonar-project.properties not found at $SONAR_PROPS"
    exit 1
fi

# Check old wrong path is gone
if grep -q 'coverage/coverage.xml' "$SONAR_PROPS"; then
    echo "FAIL: Old wrong path 'coverage/coverage.xml' still in sonar-project.properties"
    FAILED=1
else
    echo "OK: Old incorrect coverage path removed"
fi

# Check correct path is set
if grep -q 'reports/coverage.xml' "$SONAR_PROPS"; then
    echo "OK: Coverage path correctly set to reports/coverage.xml"
else
    echo "FAIL: Correct coverage path 'reports/coverage.xml' not found in sonar-project.properties"
    FAILED=1
fi

# Check coverage report file actually exists
if [ -f "$CORRECT_COVERAGE" ]; then
    echo "OK: Coverage report file exists at $CORRECT_COVERAGE"
else
    echo "FAIL: Coverage report file missing at $CORRECT_COVERAGE"
    FAILED=1
fi

# Check sonar.projectKey is set (basic config check)
if grep -q 'sonar.projectKey' "$SONAR_PROPS"; then
    echo "OK: sonar.projectKey is configured"
else
    echo "FAIL: sonar.projectKey not found in sonar-project.properties"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: SonarQube coverage path has been fixed" && exit 0
exit 1
