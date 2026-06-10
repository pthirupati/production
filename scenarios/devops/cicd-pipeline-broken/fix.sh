#!/bin/bash
set -e
cat > /opt/app/.gitlab-ci.yml <<'EOF'
stages:
  - build

build_job:
  stage: build
  image: node:18-alpine
  script:
    - npm ci
    - npm run build
EOF
