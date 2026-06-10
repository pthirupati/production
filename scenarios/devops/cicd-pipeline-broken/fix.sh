#!/bin/bash
set -e
CI=/opt/app/.gitlab-ci.yml
[ -f "$CI" ] || exit 0
sed -i 's/node:18-alpinee/node:18-alpine/g' "$CI"
grep -q 'npm ci' "$CI" || printf '
  - npm ci
' >> "$CI"
grep -q 'npm run build' "$CI" || printf '  - npm run build
' >> "$CI"
