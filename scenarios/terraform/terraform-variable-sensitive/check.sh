#!/usr/bin/env bash
# Check: Secret variables (db_password, api_key, secret) have sensitive = true.
set -euo pipefail

TF_DIR="${TF_WORKING_DIR:-/workspace/terraform}"

if [[ ! -d "$TF_DIR" ]]; then
  echo "INFO: Terraform working directory '$TF_DIR' not found — skipping check."
  exit 0
fi

# Find variable blocks with sensitive-sounding names that lack sensitive = true
ISSUES=$(python3 - "$TF_DIR" <<'PYEOF'
import os, sys, re

tf_dir = sys.argv[1]
sensitive_pattern = re.compile(r'(password|secret|token|api_key|private_key)', re.IGNORECASE)
var_block = re.compile(r'variable\s+"([^"]+)"\s*\{([^}]*)\}', re.DOTALL)

found_issues = []
for fname in os.listdir(tf_dir):
    if not fname.endswith('.tf'):
        continue
    with open(os.path.join(tf_dir, fname)) as f:
        content = f.read()
    for m in var_block.finditer(content):
        name, body = m.group(1), m.group(2)
        if sensitive_pattern.search(name) and 'sensitive' not in body:
            found_issues.append(f"{fname}: variable '{name}' missing sensitive = true")

for issue in found_issues:
    print(issue)
sys.exit(1 if found_issues else 0)
PYEOF
)

if [[ $? -ne 0 ]]; then
  echo "FAIL: Found secret variables without sensitive = true:"
  echo "$ISSUES"
  exit 1
fi

echo "PASS: All sensitive-named variables have sensitive = true."
exit 0
