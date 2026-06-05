#!/bin/bash
# Validation: .gitlab-ci.yml must be valid YAML with correct image tag
FAILED=0
CI_FILE="/opt/app/.gitlab-ci.yml"

if [ ! -f "$CI_FILE" ]; then
    echo "FAIL: .gitlab-ci.yml not found at $CI_FILE"
    exit 1
fi

if python3 -c "import yaml; yaml.safe_load(open('$CI_FILE'))" 2>/dev/null; then
    echo "OK: .gitlab-ci.yml is valid YAML"
else
    echo "FAIL: .gitlab-ci.yml has YAML syntax errors"
    FAILED=1
fi

if grep -q 'node:18-alpinee' "$CI_FILE"; then
    echo "FAIL: Image tag typo 'node:18-alpinee' still present — should be node:18-alpine"
    FAILED=1
else
    echo "OK: Docker image tag looks correct"
fi

if grep -q 'npm ci' "$CI_FILE" && grep -q 'npm run build' "$CI_FILE"; then
    echo "OK: Build script steps present"
else
    echo "FAIL: Missing required build script steps"
    FAILED=1
fi

[ $FAILED -eq 0 ] && echo "PASS: CI/CD pipeline config is fixed" && exit 0
exit 1
