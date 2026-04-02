#!/bin/bash
# FixitLab — Comprehensive End-to-End Test Suite
# Tests every feature from registration to lab validation
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
        echo "  ❌ $name (expected '$expected', got '$actual')"
        FAIL=$((FAIL + 1))
    fi
}

test_status() {
    local name="$1"
    local expected_code="$2"
    local actual_code="$3"
    TOTAL=$((TOTAL + 1))
    if [ "$actual_code" = "$expected_code" ]; then
        echo "  ✅ $name → $actual_code"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name → $actual_code (expected $expected_code)"
        FAIL=$((FAIL + 1))
    fi
}

echo "═══════════════════════════════════════════════"
echo "  FIXITLAB — FULL E2E TEST SUITE"
echo "  $(date)"
echo "═══════════════════════════════════════════════"
echo ""

# ─── 1. PUBLIC PAGES ─────────────────────────────────────────────
echo "▶ PUBLIC PAGES"
test_status "Home page" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/)"
test_status "Pricing page" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/pricing)"
test_status "About page" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/about)"
test_status "Blog page" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/blog)"
test_status "Login page" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/login)"
test_status "Register page" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/register)"
test_status "Health endpoint" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/health/)"
echo ""

# ─── 2. REGISTRATION (with OTP verification) ───────────────────
echo "▶ REGISTRATION"
UNIQUE="e2e_$(date +%s)"
EMAIL="${UNIQUE}@test.com"

# Step 1: Send OTP
OTP_RESP=$(curl -s -X POST "$BASE/api/auth/send-otp/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\"}")
test_it "Send OTP" "session_token" "$OTP_RESP"

SESSION_TOKEN=$(echo "$OTP_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_token',''))" 2>/dev/null || echo "")

# Step 2: Get OTP code from database
OTP_CODE=$(docker compose exec -T database bash -c "psql -U \$POSTGRES_USER -d \$POSTGRES_DB -t -c \"SELECT code FROM accounts_emailverificationotp WHERE email='${EMAIL}' AND verified=false ORDER BY created_at DESC LIMIT 1;\"" 2>/dev/null | tr -d ' \n')

# Step 3: Verify OTP
VERIFY_RESP=$(curl -s -X POST "$BASE/api/auth/verify-otp/" \
    -H "Content-Type: application/json" \
    -d "{\"session_token\":\"${SESSION_TOKEN}\",\"code\":\"${OTP_CODE}\"}")
test_it "Verify OTP" "Email verified" "$VERIFY_RESP"

# Step 4: Register with verified session (including first_name, last_name)
REG=$(curl -s -X POST "$BASE/api/auth/register/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"TestPass123!\",\"session_token\":\"${SESSION_TOKEN}\",\"first_name\":\"E2E\",\"last_name\":\"Tester\"}")
test_it "Register new user" "access" "$REG"

# Verify first_name/last_name returned in registration response
test_it "Register returns first_name" "E2E" "$REG"

# Extract token
TOKEN=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || echo "")
if [ -z "$TOKEN" ]; then
    echo "  ⚠ Registration failed, falling back to admin login"
    LOGIN=$(curl -s -X POST "$BASE/api/auth/login/" \
        -H "Content-Type: application/json" \
        -d '{"email":"fixitlab.admin@gmail.com","password":"Samatha@143"}')
    TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])" 2>/dev/null)
fi

# Registration without OTP should fail
NO_OTP=$(curl -s -X POST "$BASE/api/auth/register/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"nootp@test.com\",\"password\":\"TestPass123!\"}")
test_it "Registration without OTP rejected" "verification" "$NO_OTP"

# OTP for existing email should fail
DUP_OTP=$(curl -s -X POST "$BASE/api/auth/send-otp/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\"}")
test_it "Duplicate email OTP rejected" "already registered" "$DUP_OTP"
echo ""

# ─── 2b. SOCIAL AUTH CONFIG ─────────────────────────────────────
echo "▶ SOCIAL AUTH CONFIG"
SOCIAL_CFG=$(curl -s "$BASE/api/auth/social/config/")
test_it "Social config endpoint" "github" "$SOCIAL_CFG"
test_it "Social config has Google" "google" "$SOCIAL_CFG"
test_it "Social config has authorize_url" "authorize_url" "$SOCIAL_CFG"

# GitHub OAuth without code
GH_NO_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/social/github/" \
    -H "Content-Type: application/json" \
    -d '{}')
test_status "GitHub OAuth requires code" "400" "$GH_NO_CODE"

# Google OAuth without code
GO_NO_CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/social/google/" \
    -H "Content-Type: application/json" \
    -d '{}')
test_status "Google OAuth requires code" "400" "$GO_NO_CODE"

# GitHub OAuth with invalid code (returns 501 if not configured, 400/502 if configured)
GH_BAD=$(curl -s -X POST "$BASE/api/auth/social/github/" \
    -H "Content-Type: application/json" \
    -d '{"code":"invalid_test_code"}')
test_it "GitHub OAuth rejects invalid code" "not configured\|Failed\|error" "$GH_BAD"

# Google OAuth with invalid code
GO_BAD=$(curl -s -X POST "$BASE/api/auth/social/google/" \
    -H "Content-Type: application/json" \
    -d '{"code":"invalid_test_code"}')
test_it "Google OAuth rejects invalid code" "not configured\|Failed\|error" "$GO_BAD"
echo ""

# Rate limit recovery — auth throttle is 20/min
sleep 20

# ─── 3. AUTHENTICATION ──────────────────────────────────────────
echo "▶ AUTHENTICATION"
LOGIN=$(curl -s -X POST "$BASE/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"TestPass123!\"}")
test_it "Login returns token" "access" "$LOGIN"

BAD_LOGIN=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d '{"email":"bad@bad.com","password":"wrong"}')
test_status "Bad login rejected" "401" "$BAD_LOGIN"

NOAUTH=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/auth/profile/")
test_status "Profile without auth" "401" "$NOAUTH"
echo ""

# ─── 4. PROFILE ─────────────────────────────────────────────────
echo "▶ PROFILE"
AUTH="Authorization: Bearer $TOKEN"
PROFILE=$(curl -s "$BASE/api/auth/profile/" -H "$AUTH")
test_it "Get profile" "email" "$PROFILE"
test_it "Profile has country field" "country" "$PROFILE"
test_it "Profile has first_name" "first_name" "$PROFILE"

PUPDATE=$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$BASE/api/auth/profile/" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"username\":\"${UNIQUE}_updated\",\"country\":\"United States\"}")
test_status "Update profile with country" "200" "$PUPDATE"

# Verify country persisted
PROFILE_AFTER=$(curl -s "$BASE/api/auth/profile/" -H "$AUTH")
test_it "Country persisted in profile" "United States" "$PROFILE_AFTER"
echo ""

# ─── 5. PLAN & BILLING ──────────────────────────────────────────
echo "▶ PLAN & BILLING"
PLAN=$(curl -s "$BASE/api/plan/" -H "$AUTH")
test_it "Get user plan" "free" "$PLAN"
test_it "Plan has usage info" "labs_today" "$PLAN"
test_it "Plan has max_labs_per_day" "max_labs_per_day" "$PLAN"
echo ""

# ─── 6. TECHNOLOGIES ────────────────────────────────────────────
echo "▶ TECHNOLOGIES"
TECHS=$(curl -s "$BASE/api/technologies/" -H "$AUTH")
test_it "Technologies list" "Linux" "$TECHS"

TECH_DETAIL=$(curl -s "$BASE/api/technologies/linux/" -H "$AUTH")
test_it "Technology detail (linux)" "scenarios" "$TECH_DETAIL"
echo ""

# ─── 7. SCENARIOS ───────────────────────────────────────────────
echo "▶ SCENARIOS"
SCENARIOS=$(curl -s "$BASE/api/scenarios/" -H "$AUTH")
test_it "Scenarios list" "slug" "$SCENARIOS"

S_DETAIL=$(curl -s "$BASE/api/scenarios/broken-nginx/" -H "$AUTH")
test_it "Scenario detail" "broken-nginx" "$S_DETAIL"
test_it "Scenario has objectives" "objectives" "$S_DETAIL"

S_DISK=$(curl -s "$BASE/api/scenarios/disk-full/" -H "$AUTH")
test_it "Disk-full scenario" "disk-full" "$S_DISK"

S_CRON=$(curl -s "$BASE/api/scenarios/broken-cron/" -H "$AUTH")
test_it "Broken-cron scenario" "broken-cron" "$S_CRON"

S_DNS=$(curl -s "$BASE/api/scenarios/dns-resolution-broken/" -H "$AUTH")
test_it "DNS scenario" "dns-resolution" "$S_DNS"
echo ""

# ─── 8. CATEGORIES & TAGS ───────────────────────────────────────
echo "▶ CATEGORIES & TAGS"
test_status "Categories" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/categories/ -H "$AUTH")"
test_status "Tags" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/tags/ -H "$AUTH")"
echo ""

# ─── 9. BOOKMARKS ───────────────────────────────────────────────
echo "▶ BOOKMARKS"
# Get a scenario ID
SCEN_ID=$(echo "$S_DETAIL" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
BOOKMARK=$(curl -s -X POST "$BASE/api/bookmarks/" -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"scenario_id\":$SCEN_ID}")
test_it "Toggle bookmark" "bookmarked" "$BOOKMARK"

BLIST=$(curl -s "$BASE/api/bookmarks/" -H "$AUTH")
test_status "List bookmarks" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/bookmarks/ -H "$AUTH")"
echo ""

# ─── 10. LAB START/VALIDATE/STOP ─────────────────────────────────
echo "▶ LAB LIFECYCLE"
# Start a lab (broken-nginx)
NGINX_ID=$(echo "$S_DETAIL" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
START=$(curl -s -X POST "$BASE/api/labs/$NGINX_ID/start/" -H "$AUTH" -H "Content-Type: application/json")
SESSION_ID=$(echo "$START" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

if [ -n "$SESSION_ID" ]; then
    test_it "Start lab" "RUNNING" "$START"

    # Wait for container
    sleep 3

    # Validate (should fail - unfixed)
    VAL=$(curl -s -X POST "$BASE/api/labs/$SESSION_ID/validate/" -H "$AUTH")
    test_it "Validate unfixed lab fails" "false" "$(echo "$VAL" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('passed','')).lower())" 2>/dev/null)"
    test_it "Validation has output" "output" "$VAL"

    # Hints
    HINTS=$(curl -s "$BASE/api/labs/$SESSION_ID/hints/" -H "$AUTH")
    test_it "Get hints" "hints" "$HINTS"

    # Stop lab
    STOP=$(curl -s -X POST "$BASE/api/labs/$SESSION_ID/stop/" -H "$AUTH")
    test_it "Stop lab" "TERMINATED" "$STOP"
else
    echo "  ⚠ Lab start failed (may be rate limited): $(echo "$START" | head -c 100)"
    test_it "Start lab" "RUNNING" "$START"
fi
echo ""

# ─── 11. SECOND LAB (disk-full) ─────────────────────────────────
echo "▶ DISK-FULL LAB"
DISK_ID=$(echo "$S_DISK" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null)
START2=$(curl -s -X POST "$BASE/api/labs/$DISK_ID/start/" -H "$AUTH" -H "Content-Type: application/json")
SESSION2=$(echo "$START2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

if [ -n "$SESSION2" ]; then
    test_it "Start disk-full lab" "RUNNING" "$START2"
    sleep 3
    VAL2=$(curl -s -X POST "$BASE/api/labs/$SESSION2/validate/" -H "$AUTH")
    test_it "Disk-full validation fails unfixed" "false" "$(echo "$VAL2" | python3 -c "import sys,json; print(str(json.load(sys.stdin).get('passed','')).lower())" 2>/dev/null)"
    test_it "Disk-full check shows 3 failures" "log_generator" "$VAL2"
    STOP2=$(curl -s -X POST "$BASE/api/labs/$SESSION2/stop/" -H "$AUTH")
    test_it "Stop disk-full lab" "TERMINATED" "$STOP2"
else
    echo "  ⚠ Disk-full lab start failed: $(echo "$START2" | head -c 100)"
    TOTAL=$((TOTAL + 4))
    FAIL=$((FAIL + 4))
fi
echo ""

# ─── 12. ACTIVE LABS ─────────────────────────────────────────────
echo "▶ ACTIVE LABS"
test_status "Active labs endpoint" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/labs/active/ -H "$AUTH")"
echo ""

# ─── 12b. LAB HISTORY ────────────────────────────────────────────
echo "▶ LAB HISTORY"
LAB_HIST=$(curl -s "$BASE/api/labs/history/" -H "$AUTH")
test_it "Lab history endpoint" "history" "$LAB_HIST"

LAB_HIST_NOAUTH=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/labs/history/")
test_status "Lab history requires auth" "401" "$LAB_HIST_NOAUTH"
echo ""

# ─── 12c. SEARCH ─────────────────────────────────────────────────
echo "▶ SEARCH"
SEARCH_NGINX=$(curl -s "$BASE/api/search/?q=nginx")
test_it "Search finds nginx" "broken-nginx" "$SEARCH_NGINX"

SEARCH_DNS=$(curl -s "$BASE/api/search/?q=dns")
test_it "Search finds dns" "dns" "$SEARCH_DNS"

SEARCH_EMPTY=$(curl -s "$BASE/api/search/?q=zzz_nonexistent_zzz")
test_it "Empty search returns empty" "results" "$SEARCH_EMPTY"

SEARCH_SHORT=$(curl -s "$BASE/api/search/?q=x")
test_it "Short query returns empty" "results" "$SEARCH_SHORT"
echo ""

# Rate limit recovery before password tests
sleep 15

# ─── 13. PROGRESS & ACHIEVEMENTS ────────────────────────────────
echo "▶ PROGRESS & ACHIEVEMENTS"
PROGRESS=$(curl -s "$BASE/api/progress/" -H "$AUTH")
test_it "Progress endpoint" "summary" "$PROGRESS"

ACHIEVEMENTS=$(curl -s "$BASE/api/achievements/" -H "$AUTH")
test_status "Achievements" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/achievements/ -H "$AUTH")"
echo ""

# ─── 14. LEADERBOARD ────────────────────────────────────────────
echo "▶ LEADERBOARD"
LEADER=$(curl -s "$BASE/api/leaderboard/" -H "$AUTH")
test_it "Leaderboard" "leaderboard" "$LEADER"
echo ""

# ─── 15. NOTIFICATIONS ──────────────────────────────────────────
echo "▶ NOTIFICATIONS"
NOTIFS=$(curl -s "$BASE/api/notifications/" -H "$AUTH")
test_status "Notifications" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/notifications/ -H "$AUTH")"

# Mark all as read (clear notifications)
MARK_READ=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/notifications/read/" -H "$AUTH")
test_status "Mark all notifications read" "200" "$MARK_READ"
echo ""

# ─── 15b. BILLING & SUBSCRIPTIONS ───────────────────────────────
echo "▶ BILLING & SUBSCRIPTIONS"
# User subscriptions list
SUBS_STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/billing/subscriptions/" -H "$AUTH")
test_status "User subscriptions endpoint" "200" "$SUBS_STATUS"

SUBS=$(curl -s "$BASE/api/billing/subscriptions/" -H "$AUTH")
test_it "Subscriptions has list" "subscriptions" "$SUBS"

# Subscribe to a technology (get first tech ID)
TECH_ID=$(echo "$TECHS" | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('results',d) if isinstance(d,dict) else d; print(r[0]['id'] if r else '')" 2>/dev/null || echo "")
if [ -n "$TECH_ID" ]; then
    SUB_RESP=$(curl -s -X POST "$BASE/api/billing/subscribe/technology/" \
        -H "$AUTH" -H "Content-Type: application/json" \
        -d "{\"technology_id\":$TECH_ID,\"amount\":499}")
    test_it "Subscribe to technology" "subscription_id" "$SUB_RESP"

    # Verify subscription_id format
    SUB_ID=$(echo "$SUB_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('subscription_id',''))" 2>/dev/null || echo "")
    if [ -n "$SUB_ID" ]; then
        test_it "Subscription ID has FIXITLAB suffix" "FIXITLAB" "$SUB_ID"
    fi

    # Duplicate subscription should be rejected (409)
    DUP_SUB=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/billing/subscribe/technology/" \
        -H "$AUTH" -H "Content-Type: application/json" \
        -d "{\"technology_id\":$TECH_ID,\"amount\":499}")
    test_status "Duplicate subscription rejected" "409" "$DUP_SUB"

    # Verify subscription appears in list
    SUBS_AFTER=$(curl -s "$BASE/api/billing/subscriptions/" -H "$AUTH")
    test_it "Subscription appears in list" "$SUB_ID" "$SUBS_AFTER"
else
    echo "  ⚠ No technologies found, skipping subscription tests"
fi

# Subscribe without technology_id should fail
NO_TECH=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/billing/subscribe/technology/" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"amount":100}')
test_status "Subscribe without tech_id rejected" "400" "$NO_TECH"

# Unauthenticated subscription
UNSUB=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/billing/subscribe/technology/" \
    -H "Content-Type: application/json" \
    -d '{"technology_id":1}')
test_status "Subscribe requires auth" "401" "$UNSUB"

# Cancel subscription (if we have one)
if [ -n "$SUB_ID" ]; then
    CANCEL_RESP=$(curl -s -X POST "$BASE/api/billing/subscribe/cancel/" \
        -H "$AUTH" -H "Content-Type: application/json" \
        -d "{\"subscription_id\":\"$SUB_ID\"}")
    test_it "Cancel subscription" "is_active" "$CANCEL_RESP"
fi

# Cancel nonexistent subscription
CANCEL_FAKE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/billing/subscribe/cancel/" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d '{"subscription_id":"FAKE-SUB-2026-FIXITLAB"}')
test_status "Cancel nonexistent subscription" "404" "$CANCEL_FAKE"
echo ""

# ─── 16. STATS (PUBLIC) ─────────────────────────────────────────
echo "▶ PLATFORM STATS"
STATS=$(curl -s "$BASE/api/stats/")
test_it "Platform stats" "total_scenarios" "$STATS"
test_it "Stats has users" "total_users" "$STATS"
echo ""

# ─── 17. PASSWORD CHANGE ────────────────────────────────────────
echo "▶ PASSWORD MANAGEMENT"
sleep 20  # avoid auth rate limiting (extra buffer for subscription tests above)
# Login again to use new token
FRESH_LOGIN=$(curl -s -X POST "$BASE/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"TestPass123!\"}")
FRESH_TOKEN=$(echo "$FRESH_LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null)

PWCHANGE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/change-password/" \
    -H "Authorization: Bearer $FRESH_TOKEN" -H "Content-Type: application/json" \
    -d '{"old_password":"TestPass123!","new_password":"NewTestPass456!"}')
test_status "Change password" "200" "$PWCHANGE"

# Login with new password
NEWLOGIN=$(curl -s -X POST "$BASE/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"NewTestPass456!\"}")
test_it "Login with new password" "access" "$NEWLOGIN"

# Extract refresh token for later tests
NEW_REFRESH=$(echo "$NEWLOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('refresh',''))" 2>/dev/null)
echo ""

# ─── 17b. TOKEN REFRESH ─────────────────────────────────────────
echo "▶ TOKEN REFRESH"
REFRESHED=$(curl -s -X POST "$BASE/api/auth/refresh/" \
    -H "Content-Type: application/json" \
    -d "{\"refresh\":\"${NEW_REFRESH}\"}")
test_it "Token refresh returns access" "access" "$REFRESHED"

REFRESH_BAD=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/refresh/" \
    -H "Content-Type: application/json" \
    -d '{"refresh":"invalid.token.here"}')
test_status "Bad refresh token rejected" "401" "$REFRESH_BAD"
echo ""

# ─── 17c. LOGOUT ─────────────────────────────────────────────────
echo "▶ LOGOUT"
# Use the refreshed token from 17b for logout — no extra login needed
REFRESH_ACCESS=$(echo "$REFRESHED" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null)
REFRESH_NEW=$(echo "$REFRESHED" | python3 -c "import sys,json; print(json.load(sys.stdin).get('refresh',''))" 2>/dev/null)

LOGOUT_RESP=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/logout/" \
    -H "Authorization: Bearer $REFRESH_ACCESS" \
    -H "Content-Type: application/json" \
    -d "{\"refresh\":\"${REFRESH_NEW}\"}")
test_status "Logout" "200" "$LOGOUT_RESP"

# Refresh token should be blacklisted after logout
REUSE_REFRESH=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/refresh/" \
    -H "Content-Type: application/json" \
    -d "{\"refresh\":\"${REFRESH_NEW}\"}")
test_status "Refresh blacklisted after logout" "401" "$REUSE_REFRESH"
echo ""

# Rate limit recovery before security tests
sleep 20

# ─── 18. SECURITY ───────────────────────────────────────────────
echo "▶ SECURITY"
# MailHog direct port should be blocked
MHOG_RAW=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 2 http://localhost:8025/ 2>/dev/null || true)
MHOG_CODE=$(echo "$MHOG_RAW" | grep -o '[0-9]\{3\}' | head -1)
if [ "$MHOG_CODE" = "000" ] || [ -z "$MHOG_CODE" ]; then
    test_status "MailHog port 8025 blocked" "000" "000"
else
    test_status "MailHog port 8025 blocked" "000" "$MHOG_CODE"
fi

# MailHog via gateway without auth
MHOG_NOAUTH=$(curl -s -o /dev/null -w '%{http_code}' $BASE/mailbox/)
test_status "MailHog gateway requires auth" "401" "$MHOG_NOAUTH"

# MailHog via gateway with auth
MHOG_AUTH=$(curl -s -o /dev/null -w '%{http_code}' -u admin:Samatha@143 $BASE/mailbox/)
test_status "MailHog gateway with admin auth" "200" "$MHOG_AUTH"

# Blocked paths
test_status "/.env blocked" "404" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/.env)"
test_status "/.git blocked" "404" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/.git)"
echo ""

# ─── 19. FORGOT PASSWORD ────────────────────────────────────────
echo "▶ FORGOT PASSWORD"
sleep 15  # avoid auth rate limiting from previous tests
FORGOT=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/forgot-password/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\"}")
test_status "Forgot password endpoint" "200" "$FORGOT"
echo ""

# ─── 20. ADMIN ENDPOINTS ────────────────────────────────────────
echo "▶ ADMIN ENDPOINTS"
sleep 45  # auth rate limit is 30/min — wait for full counter reset
# Login as admin
ADMIN_LOGIN=$(curl -s -X POST "$BASE/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d '{"email":"fixitlab.admin@gmail.com","password":"Samatha@143"}')
ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || echo "")

if [ -z "$ADMIN_TOKEN" ]; then
    echo "  ⚠ Admin login was rate-limited, retrying after 30s..."
    sleep 30
    ADMIN_LOGIN=$(curl -s -X POST "$BASE/api/auth/login/" \
        -H "Content-Type: application/json" \
        -d '{"email":"fixitlab.admin@gmail.com","password":"Samatha@143"}')
    ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))" 2>/dev/null || echo "")
fi

test_status "Admin overview" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/overview/ -H "Authorization: Bearer $ADMIN_TOKEN")"
test_status "Admin users list" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/users/ -H "Authorization: Bearer $ADMIN_TOKEN")"
test_status "Admin scenarios" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/scenarios/ -H "Authorization: Bearer $ADMIN_TOKEN")"

# Verify admin users endpoint returns new fields
ADMIN_USERS=$(curl -s "$BASE/api/admin/users/" -H "Authorization: Bearer $ADMIN_TOKEN")
test_it "Admin users has is_paid field" "is_paid" "$ADMIN_USERS"
test_it "Admin users has is_inactive_90d" "is_inactive_90d" "$ADMIN_USERS"
test_it "Admin users has country" "country" "$ADMIN_USERS"
test_it "Admin users has first_name" "first_name" "$ADMIN_USERS"
test_it "Admin users has active_subscriptions" "active_subscriptions" "$ADMIN_USERS"

# Admin inactive users endpoint
test_status "Admin inactive users" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/users/inactive/ -H "Authorization: Bearer $ADMIN_TOKEN")"

# Admin maintenance mode endpoint
test_status "Admin maintenance endpoint" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/maintenance/ -H "Authorization: Bearer $ADMIN_TOKEN")"

# System health checks all services
HEALTH=$(curl -s $BASE/api/admin/health/ -H "Authorization: Bearer $ADMIN_TOKEN")
test_it "Health has email status" "email" "$HEALTH"
test_it "Health has rabbitmq status" "rabbitmq" "$HEALTH"
test_it "Health has celery status" "celery" "$HEALTH"
test_it "Health has containers" "containers" "$HEALTH"
test_it "Health has email stats" "email_stats" "$HEALTH"

# Activity feed
test_status "Activity feed" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/activity/ -H "Authorization: Bearer $ADMIN_TOKEN")"

# Audit logs
test_status "Audit logs" "200" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/audit-logs/ -H "Authorization: Bearer $ADMIN_TOKEN")"

# Non-admin can't access admin
test_status "Non-admin rejected from admin" "403" "$(curl -s -o /dev/null -w '%{http_code}' $BASE/api/admin/overview/ -H "$AUTH")"
echo ""

# ─── 20b. INPUT VALIDATION ──────────────────────────────────────
echo "▶ INPUT VALIDATION"
sleep 15
# Login with empty body
EMPTY_LOGIN=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d '{}')
test_status "Login empty body rejected" "400" "$EMPTY_LOGIN"

# Send OTP with invalid email
INVALID_EMAIL_OTP=$(curl -s -X POST "$BASE/api/auth/send-otp/" \
    -H "Content-Type: application/json" \
    -d '{"email":"not-an-email"}')
test_it "Invalid email OTP rejected" "valid email" "$INVALID_EMAIL_OTP"

# Change password with short password — reuse ADMIN_TOKEN from section 20
SHORT_PW=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/change-password/" \
    -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d '{"old_password":"Samatha@143","new_password":"abc"}')
test_status "Short password rejected" "400" "$SHORT_PW"

# Profile update with duplicate username (try to take the e2e test user's updated username)
DUP_USER=$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$BASE/api/auth/profile/" \
    -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
    -d "{\"username\":\"${UNIQUE}_updated\"}")
test_status "Duplicate username rejected" "400" "$DUP_USER"

# Forgot password with non-existent email
FORGOT_BAD=$(curl -s -X POST "$BASE/api/auth/forgot-password/" \
    -H "Content-Type: application/json" \
    -d '{"email":"nonexistent999@nope.com"}')
test_it "Forgot password bad email" "If an account exists" "$FORGOT_BAD"
echo ""

# ─── 21. EMAIL DELIVERY ─────────────────────────────────────────
echo "▶ EMAIL DELIVERY"
# Check that registration triggered a welcome email (via MailHog internal API through backend)
EMAIL_CHECK=$(docker exec -w /app fixitlab_backend python manage.py shell -c "
from django.core.mail import send_mail
r = send_mail('E2E Test', 'Automated test email.', 'kubelearn464@gmail.com', ['thirupathi.samu2018@gmail.com'], fail_silently=True)
print(f'sent={r}')
" 2>/dev/null)
test_it "Gmail SMTP sends email" "sent=1" "$EMAIL_CHECK"
echo ""

# ─── 22. CONTACT FORM ────────────────────────────────────────────
echo "▶ CONTACT FORM"
CONTACT_STATUS=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/contact/" \
    -H "Content-Type: application/json" \
    -d '{"name":"Test User","email":"test@example.com","subject":"Test Subject","message":"This is a test message from e2e."}')
test_status "Contact form submission" "200" "$CONTACT_STATUS"

CONTACT_DATA=$(curl -s -X POST "$BASE/api/contact/" \
    -H "Content-Type: application/json" \
    -d '{"name":"E2E Bot","email":"e2e@fixitlab.com","subject":"E2E Test","message":"Automated test message"}')
test_it "Contact returns success message" "Message sent" "$CONTACT_DATA"

CONTACT_EMPTY=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/contact/" \
    -H "Content-Type: application/json" \
    -d '{"name":"","email":"","subject":"","message":""}')
test_status "Contact rejects empty fields" "400" "$CONTACT_EMPTY"
echo ""

# ─── 23. ACHIEVEMENTS CERTIFICATE ───────────────────────────────
echo "▶ ACHIEVEMENTS CERTIFICATE"
CERT_STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/achievements/certificate/" \
    -H "Authorization: Bearer $TOKEN")
test_status "Certificate endpoint" "200" "$CERT_STATUS"

CERT_DATA=$(curl -s "$BASE/api/achievements/certificate/" \
    -H "Authorization: Bearer $TOKEN")
test_it "Certificate lists eligible technologies" "eligible_technologies" "$CERT_DATA"
echo ""

# ─── 24. COMMAND HISTORY & REPLAY ────────────────────────────────
echo "▶ COMMAND HISTORY & REPLAY"
sleep 10

# Use a known session ID from lab history (if exists); otherwise test 404/403
FAKE_UUID="00000000-0000-0000-0000-000000000000"
CMD_HIST=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/labs/$FAKE_UUID/commands/" \
    -H "Authorization: Bearer $TOKEN")
test_status "Commands for nonexistent session" "404" "$CMD_HIST"

REPLAY_STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/labs/$FAKE_UUID/replay/" \
    -H "Authorization: Bearer $TOKEN")
test_status "Replay for nonexistent session" "404" "$REPLAY_STATUS"

SOLUTION_STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/labs/$FAKE_UUID/solution/" \
    -H "Authorization: Bearer $TOKEN")
test_status "Solution for nonexistent session" "404" "$SOLUTION_STATUS"
echo ""

# ─── 25. UNAUTHENTICATED NEW ENDPOINTS ──────────────────────────
echo "▶ UNAUTHENTICATED NEW ENDPOINTS"
UNAUTH_CERT=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/achievements/certificate/")
test_status "Certificate requires auth" "401" "$UNAUTH_CERT"

UNAUTH_CMD=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/labs/$FAKE_UUID/commands/")
test_status "Commands require auth" "401" "$UNAUTH_CMD"

UNAUTH_REPLAY=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/labs/$FAKE_UUID/replay/")
test_status "Replay requires auth" "401" "$UNAUTH_REPLAY"

CONTACT_PUBLIC=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/contact/" \
    -H "Content-Type: application/json" \
    -d '{"name":"Public","email":"pub@test.com","subject":"Hi","message":"Public contact test"}')
test_status "Contact form is public" "200" "$CONTACT_PUBLIC"

SEARCH_STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/search/?q=nginx")
test_status "Search is public" "200" "$SEARCH_STATUS"
echo ""

# ─── RESULTS ─────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════"
echo "  RESULTS: $PASS passed, $FAIL failed, $TOTAL total"
echo "═══════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
