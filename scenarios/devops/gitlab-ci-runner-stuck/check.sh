#!/bin/bash
# Check that a GitLab runner has been registered and is running
FAILED=0
RUNNER_CONFIG="/etc/gitlab-runner/config.toml"

# Check that config file exists and has a runner registered
if [ -f "$RUNNER_CONFIG" ]; then
    echo "OK: GitLab runner config file exists"
else
    echo "FAIL: No runner config found at $RUNNER_CONFIG"
    FAILED=1
fi

# Check config has at least one [[runners]] entry
if grep -q '^\[\[runners\]\]' "$RUNNER_CONFIG" 2>/dev/null; then
    RUNNER_COUNT=$(grep -c '^\[\[runners\]\]' "$RUNNER_CONFIG")
    echo "OK: $RUNNER_COUNT runner(s) registered in config"
else
    echo "FAIL: No runners registered in $RUNNER_CONFIG"
    FAILED=1
fi

# Check runner process is running
if pgrep -x gitlab-runner > /dev/null 2>&1; then
    echo "OK: gitlab-runner process is running"
else
    echo "FAIL: gitlab-runner process not found"
    FAILED=1
fi

# Check runner service is enabled
if systemctl is-active gitlab-runner > /dev/null 2>&1; then
    echo "OK: gitlab-runner service is active"
else
    echo "WARN: gitlab-runner service not managed by systemctl (may be running directly)"
fi

[ $FAILED -eq 0 ] && echo "PASS: GitLab runner is registered and running" && exit 0
exit 1
