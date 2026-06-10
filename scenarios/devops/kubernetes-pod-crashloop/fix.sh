#!/bin/bash
set -e
MANIFEST=/opt/k8s/deployment.yaml
[ -f "$MANIFEST" ] || exit 0
sed -i 's/targetPort:[[:space:]]*8080/targetPort: 80/g' "$MANIFEST"
if ! grep -q 'containerPort:[[:space:]]*80' "$MANIFEST"; then
  sed -i 's/containerPort:[[:space:]]*[0-9]\+/containerPort: 80/g' "$MANIFEST"
fi
service nginx start 2>/dev/null || systemctl start nginx 2>/dev/null || nginx || true
