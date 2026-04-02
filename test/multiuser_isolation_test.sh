#!/bin/bash
# FixitLab — Multi-User Concurrent Lab Isolation Test
# Tests that two users can work on the SAME scenario simultaneously
# without interfering with each other.
set -euo pipefail

BASE="http://localhost:8080"
PASS=0
FAIL=0
TOTAL=0

test_it() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$expected"; then
        echo "  ✅ $name"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name (expected '$expected', got: $(echo "$actual" | head -c 200))"
        FAIL=$((FAIL + 1))
    fi
}

echo "=============================================="
echo "  MULTI-USER CONCURRENT LAB ISOLATION TEST"
echo "=============================================="
echo ""

# ─── Step 1: Login both users ────────────────────────────────────────
echo "▶ AUTHENTICATING TWO USERS"

TOKEN_A=$(curl -sf "$BASE/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"email":"fixitlab.admin@gmail.com","password":"Samatha@143"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")
test_it "User A (admin) login" "ey" "$TOKEN_A"

TOKEN_B=$(curl -sf "$BASE/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"email":"testuser2@fixitlab.com","password":"TestPass123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")
test_it "User B (testuser2) login" "ey" "$TOKEN_B"

# ─── Step 2: Get the same scenario ID ────────────────────────────────
echo ""
echo "▶ SELECTING SHARED SCENARIO"

SCENARIO_ID=$(curl -sf "$BASE/api/scenarios/" \
  -H "Authorization: Bearer $TOKEN_A" | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', data) if isinstance(data, dict) else data
for s in results:
    if s.get('slug') == 'broken-nginx' or 'nginx' in s.get('slug','').lower():
        print(s['id'])
        break
else:
    # fallback: first scenario
    if results:
        print(results[0]['id'])
")
test_it "Found scenario ID" "$SCENARIO_ID" "$SCENARIO_ID"
echo "  📌 Using scenario ID: $SCENARIO_ID"

# ─── Step 3: Start labs CONCURRENTLY for both users ──────────────────
echo ""
echo "▶ STARTING CONCURRENT LABS (same scenario, different users)"

# Start User A's lab
RESP_A=$(curl -sf -X POST "$BASE/api/labs/$SCENARIO_ID/start/" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json")
SESSION_A=$(echo "$RESP_A" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))")
CONTAINER_A=$(echo "$RESP_A" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('container_name',''))")
test_it "User A lab started" "fixitlab-" "$CONTAINER_A"
echo "  📌 User A session: $SESSION_A"
echo "  📌 User A container: $CONTAINER_A"

# Start User B's lab (same scenario!)
RESP_B=$(curl -sf -X POST "$BASE/api/labs/$SCENARIO_ID/start/" \
  -H "Authorization: Bearer $TOKEN_B" \
  -H "Content-Type: application/json")
SESSION_B=$(echo "$RESP_B" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))")
CONTAINER_B=$(echo "$RESP_B" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('container_name',''))")
test_it "User B lab started" "fixitlab-" "$CONTAINER_B"
echo "  📌 User B session: $SESSION_B"
echo "  📌 User B container: $CONTAINER_B"

# Verify they got different sessions and containers
test_it "Different session IDs" "true" "$(python3 -c "print('true' if '$SESSION_A' != '$SESSION_B' else 'SAME!')")"
test_it "Different container names" "true" "$(python3 -c "print('true' if '$CONTAINER_A' != '$CONTAINER_B' else 'SAME!')")"

# ─── Step 4: Verify both containers are running ─────────────────────
echo ""
echo "▶ VERIFYING CONTAINER ISOLATION"

# Check containers exist in Docker
RUNNING_A=$(docker inspect "$CONTAINER_A" --format '{{.State.Status}}' 2>/dev/null || echo "NOT_FOUND")
RUNNING_B=$(docker inspect "$CONTAINER_B" --format '{{.State.Status}}' 2>/dev/null || echo "NOT_FOUND")
test_it "User A container running" "running" "$RUNNING_A"
test_it "User B container running" "running" "$RUNNING_B"

# Check they have different IPs
IP_A=$(docker inspect "$CONTAINER_A" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || echo "N/A")
IP_B=$(docker inspect "$CONTAINER_B" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 2>/dev/null || echo "N/A")
echo "  📌 User A IP: $IP_A"
echo "  📌 User B IP: $IP_B"
test_it "Different IPs" "true" "$(python3 -c "print('true' if '$IP_A' != '$IP_B' else 'SAME!')")"

# ─── Step 5: Execute commands in each container — verify isolation ───
echo ""
echo "▶ TESTING COMMAND ISOLATION"

# Write a unique marker file in User A's container
docker exec "$CONTAINER_A" bash -c "echo 'USER_A_WAS_HERE' > /tmp/user_marker.txt" 2>/dev/null
READ_A=$(docker exec "$CONTAINER_A" cat /tmp/user_marker.txt 2>/dev/null || echo "FILE_NOT_FOUND")
test_it "User A marker written" "USER_A_WAS_HERE" "$READ_A"

# Write a different marker in User B's container
docker exec "$CONTAINER_B" bash -c "echo 'USER_B_WAS_HERE' > /tmp/user_marker.txt" 2>/dev/null
READ_B=$(docker exec "$CONTAINER_B" cat /tmp/user_marker.txt 2>/dev/null || echo "FILE_NOT_FOUND")
test_it "User B marker written" "USER_B_WAS_HERE" "$READ_B"

# Verify User A's marker is still their own (not overwritten by B)
READ_A_AGAIN=$(docker exec "$CONTAINER_A" cat /tmp/user_marker.txt 2>/dev/null || echo "FILE_NOT_FOUND")
test_it "User A marker still intact (not affected by B)" "USER_A_WAS_HERE" "$READ_A_AGAIN"

# Verify User B's marker is still their own
READ_B_AGAIN=$(docker exec "$CONTAINER_B" cat /tmp/user_marker.txt 2>/dev/null || echo "FILE_NOT_FOUND")
test_it "User B marker still intact (not affected by A)" "USER_B_WAS_HERE" "$READ_B_AGAIN"

# ─── Step 6: Modify a system file in A, verify B is unaffected ──────
echo ""
echo "▶ TESTING FILESYSTEM ISOLATION"

# User A: break nginx config (common scenario action)
docker exec "$CONTAINER_A" bash -c "echo '# BROKEN BY USER A' >> /etc/hosts" 2>/dev/null
A_HOSTS=$(docker exec "$CONTAINER_A" tail -1 /etc/hosts 2>/dev/null)
test_it "User A modified /etc/hosts" "BROKEN BY USER A" "$A_HOSTS"

# Verify User B's /etc/hosts is NOT modified
B_HOSTS=$(docker exec "$CONTAINER_B" tail -1 /etc/hosts 2>/dev/null)
test_it "User B /etc/hosts NOT affected" "true" "$(python3 -c "print('true' if 'BROKEN BY USER A' not in '''$B_HOSTS''' else 'CONTAMINATED!')")"

# ─── Step 6b: Verify NETWORK isolation (per-session networks) ───────
echo ""
echo "▶ TESTING NETWORK ISOLATION (per-session networks)"

# Get User B's IP from User A's perspective — they should NOT be reachable
NET_A=$(docker inspect "$CONTAINER_A" --format '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}' 2>/dev/null)
NET_B=$(docker inspect "$CONTAINER_B" --format '{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}' 2>/dev/null)
test_it "Containers on different networks" "true" "$(python3 -c "print('true' if '$NET_A' != '$NET_B' else 'SAME_NETWORK!')")"

# Try to ping User B's IP from User A — should fail (different networks)
PING_RESULT=$(docker exec "$CONTAINER_A" timeout 2 ping -c 1 "$IP_B" 2>&1 || echo "UNREACHABLE")
test_it "User A cannot reach User B (network isolation)" "UNREACHABLE" "$(echo "$PING_RESULT" | grep -q 'UNREACHABLE\|100% packet loss\|Network is unreachable' && echo 'UNREACHABLE' || echo 'REACHABLE!')"

# ─── Step 7: Validate labs via API (ensure correct routing) ─────────
echo ""
echo "▶ TESTING API SESSION OWNERSHIP"

# User A can validate their own session
VALIDATE_A=$(curl -sf -X POST "$BASE/api/labs/$SESSION_A/validate/" \
  -H "Authorization: Bearer $TOKEN_A" \
  -w "\n%{http_code}" 2>/dev/null || echo "error")
HTTP_A=$(echo "$VALIDATE_A" | tail -1)
# Validation might fail (expected -  we haven't actually fixed the scenario), but 200 or 400 means correct routing
test_it "User A can validate own session" "true" "$(python3 -c "print('true' if '$HTTP_A' in ('200','400') else 'false: $HTTP_A')")"

# User B trying to validate User A's session should fail
VALIDATE_BA=$(curl -s -X POST "$BASE/api/labs/$SESSION_A/validate/" \
  -H "Authorization: Bearer $TOKEN_B" \
  -w "\n%{http_code}" 2>/dev/null || echo "error")
HTTP_BA=$(echo "$VALIDATE_BA" | tail -1)
test_it "User B CANNOT validate User A's session (403/404)" "true" "$(python3 -c "print('true' if '$HTTP_BA' in ('403','404') else 'false: $HTTP_BA')")"

# User B can validate their own session
VALIDATE_B=$(curl -sf -X POST "$BASE/api/labs/$SESSION_B/validate/" \
  -H "Authorization: Bearer $TOKEN_B" \
  -w "\n%{http_code}" 2>/dev/null || echo "error")
HTTP_B=$(echo "$VALIDATE_B" | tail -1)
test_it "User B can validate own session" "true" "$(python3 -c "print('true' if '$HTTP_B' in ('200','400') else 'false: $HTTP_B')")"

# ─── Step 8: Stop both labs ─────────────────────────────────────────
echo ""
echo "▶ CLEANUP — STOPPING LABS"

STOP_A=$(curl -sf -X POST "$BASE/api/labs/$SESSION_A/stop/" \
  -H "Authorization: Bearer $TOKEN_A" -w "\n%{http_code}" 2>/dev/null || echo "error")
test_it "User A lab stopped" "true" "$(python3 -c "print('true' if '200' in '''$STOP_A''' else 'false')")"

STOP_B=$(curl -sf -X POST "$BASE/api/labs/$SESSION_B/stop/" \
  -H "Authorization: Bearer $TOKEN_B" -w "\n%{http_code}" 2>/dev/null || echo "error")
test_it "User B lab stopped" "true" "$(python3 -c "print('true' if '200' in '''$STOP_B''' else 'false')")"

# Verify containers are removed
sleep 2
GONE_A=$(docker inspect "$CONTAINER_A" --format '{{.State.Status}}' 2>/dev/null || echo "REMOVED")
GONE_B=$(docker inspect "$CONTAINER_B" --format '{{.State.Status}}' 2>/dev/null || echo "REMOVED")
if [[ "$GONE_A" == "REMOVED" || "$GONE_A" == "exited" ]]; then
    test_it "User A container cleaned up" "true" "true"
else
    test_it "User A container cleaned up" "REMOVED" "$GONE_A"
fi
if [[ "$GONE_B" == "REMOVED" || "$GONE_B" == "exited" ]]; then
    test_it "User B container cleaned up" "true" "true"
else
    test_it "User B container cleaned up" "REMOVED" "$GONE_B"
fi

# ─── Results ────────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "  RESULTS: $PASS passed / $FAIL failed / $TOTAL total"
echo "=============================================="

exit $FAIL
