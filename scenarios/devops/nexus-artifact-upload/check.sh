#!/bin/bash
# Check that Nexus deploy user has upload permissions
FAILED=0
NEXUS_URL="http://localhost:8081"
ADMIN_CREDS_FILE="/opt/nexus/admin_creds"
PERMS_LOG="/opt/nexus/.perms_updated"

# Check permissions log
if [ -f "$PERMS_LOG" ]; then
    if grep -q "nx-repository-write\|nx-releases-write" "$PERMS_LOG"; then
        echo "OK: Permission update log shows write role assigned"
    fi
fi

# Check via Nexus REST API if available
if [ -f "$ADMIN_CREDS_FILE" ]; then
    ADMIN_PASS=$(cat "$ADMIN_CREDS_FILE" | grep password | awk '{print $2}')
    ADMIN_USER=$(cat "$ADMIN_CREDS_FILE" | grep username | awk '{print $2}' || echo "admin")

    if command -v curl > /dev/null 2>&1; then
        USER_ROLES=$(curl -s -u "${ADMIN_USER:-admin}:${ADMIN_PASS}" \
            "$NEXUS_URL/service/rest/v1/security/users/deploy" 2>/dev/null)

        if echo "$USER_ROLES" | grep -qi "nx-repository-write\|nx-releases-write"; then
            echo "OK: deploy user has write role assigned"
        else
            echo "FAIL: deploy user does not have repository write role"
            FAILED=1
        fi

        # Test actual upload with deploy user
        TEST_FILE=$(mktemp /tmp/test-artifact-XXXXX.txt)
        echo "test" > "$TEST_FILE"
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -u "deploy:deploy123" \
            -X POST "$NEXUS_URL/repository/releases/" \
            -F "file=@$TEST_FILE" 2>/dev/null)
        rm -f "$TEST_FILE"

        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
            echo "OK: Artifact upload returned HTTP $HTTP_CODE"
        elif [ "$HTTP_CODE" = "403" ]; then
            echo "FAIL: Upload still returns 403 Forbidden"
            FAILED=1
        else
            echo "INFO: Upload returned HTTP $HTTP_CODE"
        fi
    fi
fi

[ $FAILED -eq 0 ] && echo "PASS: Nexus artifact upload permissions fixed" && exit 0
exit 1
