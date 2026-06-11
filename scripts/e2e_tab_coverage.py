"""
Full UI tab / feature / option coverage for FixitLab E2E tests.
Maps every main sidebar tab, admin tab, and API surface used by the frontend.
"""
from __future__ import annotations

import os
import uuid

from e2e_production_test import (
    SKIP_LAB,
    api,
    err_msg,
    login,
)

# ── Coverage manifest (every frontend tab → test function) ─────────────
UI_COVERAGE = {
    "public": [
        "Home stats/technologies", "Search", "Contact", "Certificate verify",
        "Billing gateway/currency", "Social auth config", "Health/config",
    ],
    "auth": [
        "Register OTP flow", "Login", "Profile GET/PUT", "Change password path",
        "Forgot password", "Token refresh", "Logout",
    ],
    "dashboard": ["Progress", "Achievements", "Active labs", "Subscriptions", "Jira tickets"],
    "technologies": ["List", "Detail by slug", "Scenarios per tech"],
    "scenarios": ["List filters", "Detail slug", "Bookmark toggle", "Ratings"],
    "lab_runner": ["Start", "Status", "Hints GET/POST", "Validate", "Commands", "Replay", "Solution", "Stop"],
    "leaderboard": ["Global", "Per technology"],
    "bookmarks": ["List", "Toggle"],
    "lab_history": ["History list"],
    "achievements": ["List", "Certificate endpoint"],
    "community": ["List", "Create", "Detail", "Reply", "Vote", "Delete own thread"],
    "profile": ["Profile", "Plan", "Notification prefs GET/PATCH"],
    "notifications": ["List", "Mark read", "Mark all read"],
    "billing": ["Gateway", "Subscriptions", "Status", "Currency", "Razorpay order (dry)"],
    "jira": ["User tickets", "Scenario ticket GET/POST", "Webhook security"],
    "admin_overview": ["Overview", "Health", "Analytics", "Activity"],
    "admin_scenarios": ["List", "Tags", "Detail"],
    "admin_jira": ["Tickets", "Sync param"],
    "admin_technologies": ["Technologies", "Tags"],
    "admin_users": ["List", "Inactive", "Detail", "Export CSV"],
    "admin_labs": ["Active", "Terminate idle"],
    "admin_subscriptions": ["Logs", "Subscription-logs"],
    "admin_threads": ["List", "Detail"],
    "admin_settings": ["Config", "Maintenance GET/POST", "Tag CRUD", "Admin thread mod", "Jira create"],
    "question_bank": ["Technologies API", "Scenarios API"],
    "frontend_pages": ["Static/marketing routes HTTP 200"],
}


def _batch(s, prefix: str, cases: list, token: str | None = None):
    """cases: [(method, path, body|None, ok_statuses_tuple, short_name)]"""
    for item in cases:
        method, path = item[0], item[1]
        body = item[2] if len(item) > 2 else None
        ok = item[3] if len(item) > 3 else (200,)
        name = item[4] if len(item) > 4 else f"{method} {path}"
        st, data = api(method, path, token=token, data=body)
        s.record(f"{prefix} {name}", st in ok, st, err_msg(data))


def grant_test_subscriptions(email: str) -> bool:
    """Give E2E user access to all technologies (matches lab validation setup)."""
    try:
        import django
        import os
        import sys

        sys.path.insert(0, "/app")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        from django.contrib.auth import get_user_model
        from apps.question_bank.models import Technology
        from apps.billing.models import Plan, Subscription, TechnologySubscription

        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if not user:
            return False
        plan, _ = Plan.objects.get_or_create(
            code="e2e-unlimited",
            defaults={
                "name": "E2E Unlimited",
                "price": 0,
                "max_labs_per_day": 9999,
                "max_lab_duration_minutes": 120,
            },
        )
        Subscription.objects.update_or_create(user=user, defaults={"plan": plan, "is_active": True})
        for tech in Technology.objects.filter(is_active=True):
            TechnologySubscription.objects.get_or_create(
                user=user,
                technology=tech,
                defaults={
                    "subscription_id": f"E2E-{user.username[:12]}-{tech.id}-TEST",
                    "is_active": True,
                    "amount": 0,
                    "payment_verified": True,
                },
            )
        return True
    except Exception:
        return False


def run_search_and_public_extras(s):
    print("\n=== [Public] Search & certificate ===")
    _batch(s, "Public", [
        ("GET", "/api/search/?q=docker", None, (200,), "search docker"),
        ("GET", "/api/search/?q=linux", None, (200,), "search linux"),
        ("GET", "/api/achievements/certificate/verify/?certificate_id=INVALID", None, (200,), "cert verify invalid"),
        ("GET", "/api/billing/status/", None, (200, 401), "billing status"),
    ])


def run_auth_token_flow(s, token: str, email: str, password: str, refresh_hint: str = ""):
    print("\n=== [Auth] Refresh & logout ===")
    refresh = refresh_hint
    if not refresh:
        for _ in range(2):
            _, login_data = login(email, password)
            refresh = (login_data or {}).get("refresh", "")
            if refresh:
                break
    if refresh:
        st, refresh_data = api("POST", "/api/auth/refresh/", data={"refresh": refresh})
        s.record("Auth refresh token", st in (200, 429), st)
        if st == 200 and isinstance(refresh_data, dict) and refresh_data.get("refresh"):
            refresh = refresh_data["refresh"]
    else:
        s.record("Auth refresh token", False, detail="no refresh in login")

    st, _ = api("POST", "/api/auth/change-password/", token=token, data={
        "old_password": password,
        "new_password": password,
    })
    s.record("Auth change-password", st in (200, 400), st)

    st, _ = api("POST", "/api/auth/logout/", token=token, data={"refresh": refresh})
    s.record("Auth logout", st in (200, 204, 400), st)
    # Re-login for remaining tests
    new_token, _ = login(email, password)
    return new_token or token


def run_dashboard_tab(s, token: str):
    print("\n=== [Tab] Dashboard ===")
    _batch(s, "Dashboard", [
        ("GET", "/api/progress/", None, (200,), "progress"),
        ("GET", "/api/achievements/", None, (200,), "achievements"),
        ("GET", "/api/labs/active/", None, (200,), "active labs"),
        ("GET", "/api/billing/subscriptions/", None, (200,), "subscriptions"),
        ("GET", "/api/jira/tickets/", None, (200,), "jira tickets"),
        ("GET", "/api/plan/", None, (200,), "plan usage"),
    ], token)


def run_technologies_tab(s, token: str):
    print("\n=== [Tab] Technologies ===")
    st, techs = api("GET", "/api/technologies/", token=token)
    s.record("Technologies list", st == 200, st)
    if st != 200 or not techs:
        return
    items = techs if isinstance(techs, list) else techs.get("results", techs)
    for tech in items[:5]:
        slug = tech.get("slug", "")
        if not slug:
            continue
        st, _ = api("GET", f"/api/technologies/{slug}/", token=token)
        s.record(f"Technology detail {slug}", st == 200, st)


def run_scenarios_tab(s, token: str) -> dict | None:
    print("\n=== [Tab] Scenarios (filters, detail, bookmark, ratings) ===")
    _batch(s, "Scenarios", [
        ("GET", "/api/scenarios/?difficulty=easy", None, (200,), "filter easy"),
        ("GET", "/api/scenarios/?free=true", None, (200,), "filter free"),
        ("GET", "/api/scenarios/?search=linux", None, (200,), "filter search"),
        ("GET", "/api/categories/", None, (200,), "categories"),
        ("GET", "/api/tags/", None, (200,), "tags"),
    ], token)

    st, data = api("GET", "/api/scenarios/?limit=5", token=token)
    items = data if isinstance(data, list) else (data.get("results") if isinstance(data, dict) else []) or []
    scenario = next((x for x in items if x.get("is_active")), items[0] if items else None)
    if not scenario:
        s.record("Scenarios pick active", False, detail="none found")
        return None

    sid = scenario.get("id")
    slug = scenario.get("slug", "")
    st, _ = api("GET", f"/api/scenarios/{slug}/", token=token)
    s.record(f"Scenario detail {slug}", st == 200, st)

    st, bm = api("POST", "/api/bookmarks/", token=token, data={"scenario_id": sid})
    s.record("Bookmark toggle on", st in (200, 201), st)
    api("POST", "/api/bookmarks/", token=token, data={"scenario_id": sid})

    st, _ = api("GET", f"/api/ratings/?type=scenario&scenario={sid}", token=token)
    s.record("Ratings list scenario", st == 200, st)
    st, _ = api("POST", "/api/ratings/rate/", token=token, data={
        "rating_type": "scenario", "scenario": sid, "score": 5, "review": "E2E test review",
    })
    s.record("Ratings submit", st in (200, 201), st)

    st, _ = api("GET", f"/api/jira/tickets/scenario/{sid}/?details=1", token=token)
    s.record("Jira scenario ticket GET", st == 200, st)
    st, _ = api("POST", f"/api/jira/tickets/scenario/{sid}/", token=token)
    s.record("Jira scenario ticket POST", st in (200, 201), st)

    return scenario


def run_leaderboard_tab(s, token: str):
    print("\n=== [Tab] Leaderboard ===")
    _batch(s, "Leaderboard", [
        ("GET", "/api/leaderboard/", None, (200,), "global"),
    ], token)
    st, techs = api("GET", "/api/technologies/", token=token)
    if st == 200 and techs:
        items = techs if isinstance(techs, list) else techs
        if items:
            tid = items[0].get("id")
            st, _ = api("GET", f"/api/leaderboard/?technology={tid}", token=token)
            s.record("Leaderboard by technology", st == 200, st)


def run_bookmarks_tab(s, token: str):
    print("\n=== [Tab] Bookmarks ===")
    _batch(s, "Bookmarks", [
        ("GET", "/api/bookmarks/", None, (200,), "list"),
    ], token)


def run_lab_history_tab(s, token: str):
    print("\n=== [Tab] Lab History ===")
    _batch(s, "LabHistory", [
        ("GET", "/api/labs/history/", None, (200,), "history"),
    ], token)


def run_achievements_tab(s, token: str):
    print("\n=== [Tab] Achievements ===")
    _batch(s, "Achievements", [
        ("GET", "/api/achievements/", None, (200,), "list"),
        ("GET", "/api/achievements/certificate/", None, (200, 400, 404), "certificate"),
    ], token)
    st, techs = api("GET", "/api/technologies/", token=token)
    if st == 200 and techs:
        items = techs if isinstance(techs, list) else techs
        if items:
            slug = items[0].get("slug", "")
            st, _ = api("GET", f"/api/achievements/certificate/?technology={slug}", token=token)
            s.record(f"Certificate tech {slug}", st in (200, 400, 404), st)


def run_profile_tab(s, token: str):
    print("\n=== [Tab] Profile (all sections) ===")
    _batch(s, "Profile", [
        ("GET", "/api/auth/profile/", None, (200,), "profile GET"),
        ("PUT", "/api/auth/profile/", {"first_name": "E2E", "last_name": "Tester"}, (200,), "profile PUT"),
        ("GET", "/api/plan/", None, (200,), "plan usage"),
        ("GET", "/api/notifications/preferences/", None, (200,), "notif prefs GET"),
        ("PATCH", "/api/notifications/preferences/", {
            "email_lab_completed": True,
            "email_achievements": True,
            "in_app_enabled": True,
        }, (200,), "notif prefs PATCH"),
    ], token)


def run_notifications_tab(s, token: str):
    print("\n=== [Tab] Notifications bell ===")
    st, data = api("GET", "/api/notifications/", token=token)
    s.record("Notifications list", st == 200, st)
    if st == 200 and isinstance(data, dict):
        notifs = data.get("results") or data.get("notifications") or []
        if notifs and isinstance(notifs, list):
            nid = notifs[0].get("id")
            if nid:
                st, _ = api("POST", f"/api/notifications/{nid}/read/", token=token)
                s.record("Notification mark read", st in (200, 204), st)
    st, _ = api("POST", "/api/notifications/read/", token=token, data={})
    s.record("Notifications mark all read", st in (200, 204), st)


def run_billing_all_options(s, token: str):
    print("\n=== [Tab] Billing & payment options ===")
    _batch(s, "Billing", [
        ("GET", "/api/billing/gateway-status/", None, (200,), "gateway status"),
        ("GET", "/api/billing/subscriptions/", None, (200,), "subscriptions"),
        ("GET", "/api/billing/currency-rate/", None, (200,), "currency rate"),
        ("GET", "/api/billing/subscription-logs/", None, (200, 403), "subscription logs"),
    ], token)
    st, techs = api("GET", "/api/technologies/", token=token)
    if st == 200 and techs:
        items = techs if isinstance(techs, list) else techs
        paid = next((t for t in items if not t.get("is_free", True)), items[0] if items else None)
        if paid:
            st, _ = api("POST", "/api/billing/razorpay/order/", token=token, data={
                "technology_id": paid.get("id"),
                "currency": "INR",
            })
            s.record("Razorpay order create", st in (200, 201, 400, 409, 429, 503), st)


def run_community_full(s, token: str):
    print("\n=== [Tab] Community (thread, reply, vote, delete) ===")
    st, data = api("GET", "/api/community/threads/", token=token)
    s.record("Community thread list", st == 200, st)

    st, thread = api("POST", "/api/community/threads/", token=token, data={
        "title": f"E2E full coverage {uuid.uuid4().hex[:6]}",
        "body": "Automated community E2E — all options tested",
    })
    s.record("Community create thread", st in (200, 201), st)
    thread_id = (thread or {}).get("id")
    if not thread_id:
        return None

    st, detail = api("GET", f"/api/community/threads/{thread_id}/", token=token)
    s.record("Community thread detail", st == 200, st)

    st, reply = api("POST", f"/api/community/threads/{thread_id}/replies/", token=token, data={
        "body": "E2E reply text",
    })
    s.record("Community post reply", st in (200, 201), st)
    reply_id = (reply or {}).get("id")

    st, _ = api("POST", f"/api/community/threads/{thread_id}/vote/", token=token, data={"vote_type": "up"})
    s.record("Community thread upvote", st in (200, 201), st)
    st, _ = api("POST", f"/api/community/threads/{thread_id}/vote/", token=token, data={"vote_type": "down"})
    s.record("Community thread downvote", st in (200, 201, 400), st)

    st, _ = api("PATCH", f"/api/community/threads/{thread_id}/", token=token, data={
        "title": f"E2E updated {uuid.uuid4().hex[:4]}",
    })
    s.record("Community edit thread", st in (200,), st)

    if reply_id:
        st, _ = api("POST", f"/api/community/replies/{reply_id}/vote/", token=token, data={"vote_type": "up"})
        s.record("Community reply upvote", st in (200, 201), st)
        st, _ = api("PATCH", f"/api/community/replies/{reply_id}/", token=token, data={"body": "E2E edited reply"})
        s.record("Community edit reply", st in (200,), st)
        st, _ = api("DELETE", f"/api/community/replies/{reply_id}/", token=token)
        s.record("Community delete reply", st in (200, 204), st)

    st, _ = api("DELETE", f"/api/community/threads/{thread_id}/", token=token)
    s.record("Community delete own thread", st in (200, 204), st)
    return None  # thread removed by user; admin mod tests use separate flow


def _run_community_admin_mod(s, admin_token: str, user_token: str):
    """Admin: pin/lock/reply/delete on a test thread."""
    st, thread = api("POST", "/api/community/threads/", token=user_token, data={
        "title": f"E2E admin mod {uuid.uuid4().hex[:6]}",
        "body": "Thread for admin moderation E2E",
    })
    if st not in (200, 201) or not (thread or {}).get("id"):
        s.record("Admin mod setup thread", False, st)
        return
    tid = thread["id"]
    st, _ = api("PATCH", f"/api/admin/threads/{tid}/", token=admin_token, data={
        "is_pinned": True, "is_locked": False,
    })
    s.record("Admin thread pin PATCH", st in (200,), st)
    st, _ = api("POST", f"/api/admin/threads/{tid}/", token=admin_token, data={
        "body": "Admin moderation reply E2E",
    })
    s.record("Admin thread reply POST", st in (200, 201), st)
    st, _ = api("DELETE", f"/api/admin/threads/{tid}/", token=admin_token)
    s.record("Admin thread soft DELETE", st in (200, 204), st)


def run_forgot_password(s, email: str):
    print("\n=== [Auth] Forgot password ===")
    st, _ = api("POST", "/api/auth/forgot-password/", data={"email": email})
    s.record("Forgot password", st in (200, 202), st)


def run_question_bank_api(s, token: str):
    print("\n=== [API] Question bank router ===")
    _batch(s, "QuestionBank", [
        ("GET", "/api/question_bank/technologies/", None, (200,), "technologies"),
        ("GET", "/api/question_bank/scenarios/", None, (200,), "scenarios"),
    ], token)


def run_frontend_static_pages(s):
    """Marketing/SPA routes — expect HTTP 200 from site root (not API BASE_URL)."""
    site = os.environ.get("SITE_URL", "").rstrip("/")
    if not site or site.startswith("http://127.0.0.1") or site.startswith("http://backend"):
        s.record("Frontend static pages", True, detail="skipped (no SITE_URL)")
        return
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
    paths = [
        "/", "/login", "/register", "/pricing", "/about", "/contact", "/faq",
        "/privacy", "/terms", "/blog", "/forgot-password", "/technologies",
        "/scenarios", "/leaderboard", "/verify-certificate",
    ]
    print("\n=== [Frontend] Static & SPA routes ===")
    for path in paths:
        url = f"{site}{path}"
        try:
            req = Request(url, headers={"Accept": "text/html"})
            with urlopen(req, timeout=20) as resp:
                ok = resp.status == 200
                s.record(f"Page {path}", ok, resp.status)
        except HTTPError as e:
            s.record(f"Page {path}", e.code in (200, 304), e.code)
        except URLError as e:
            s.record(f"Page {path}", False, detail=str(e.reason)[:40])


def run_admin_write_ops(s, admin_token: str, test_user_id: int | None, scenario_id: int | None):
    print("\n=== [Admin] Write operations (create/update/delete) ===")
    tag_name = f"E2E-Cleanup-{uuid.uuid4().hex[:8]}"
    st, tag = api("POST", "/api/admin/tags/", token=admin_token, data={"name": tag_name})
    s.record("Admin tag CREATE", st in (200, 201), st)
    tag_id = (tag or {}).get("id")
    if tag_id:
        st, _ = api("PUT", f"/api/admin/tags/{tag_id}/", token=admin_token, data={"name": f"{tag_name}-renamed"})
        s.record("Admin tag UPDATE", st in (200,), st)
        st, _ = api("DELETE", f"/api/admin/tags/{tag_id}/", token=admin_token)
        s.record("Admin tag DELETE", st in (200, 204), st)

    st, maint = api("GET", "/api/admin/maintenance/", token=admin_token)
    orig_enabled = (maint or {}).get("maintenance_mode", False)
    orig_msg = (maint or {}).get("maintenance_message", "")
    st, _ = api("POST", "/api/admin/maintenance/", token=admin_token, data={
        "enabled": False, "message": orig_msg or "E2E test",
    })
    s.record("Admin maintenance POST", st in (200,), st)
    api("POST", "/api/admin/maintenance/", token=admin_token, data={
        "enabled": orig_enabled, "message": orig_msg,
    })

    if test_user_id and scenario_id:
        st, jira = api("POST", "/api/admin/jira/tickets/create/", token=admin_token, data={
            "user_id": test_user_id,
            "scenario_id": scenario_id,
        })
        s.record("Admin Jira ticket CREATE", st in (200, 201), st,
                 (jira or {}).get("issue_key", "")[:20])


def run_billing_subscribe_cancel_user(s, token: str):
    st, _ = api("POST", "/api/billing/subscribe/cancel/", token=token, data={})
    s.record("Billing subscribe cancel (user)", st in (200, 400, 404), st)


def run_lab_runner_all_tabs(s, token: str, scenario: dict | None) -> None:
    print("\n=== [Tab] Lab Runner (Instructions/Hints/Result APIs) ===")
    if os.environ.get("E2E_SKIP_DUPLICATE_LABS") == "1":
        s.record("Lab runner tabs", True, detail="covered by e2e_all_scenarios_labs.py")
        return
    if SKIP_LAB:
        s.record("Lab runner tabs", True, detail="skipped E2E_SKIP_LAB=1")
        return
    if not scenario:
        st, data = api("GET", "/api/scenarios/?limit=3", token=token)
        items = data if isinstance(data, list) else (data.get("results") if isinstance(data, dict) else []) or []
        scenario = next((x for x in items if x.get("is_active")), items[0] if items else None)
    if not scenario:
        s.record("Lab runner scenario", False, detail="no scenario")
        return

    sid = scenario.get("id")
    st, data = api("POST", f"/api/labs/{sid}/start/", token=token)
    s.record("Lab start", st in (200, 201, 202), st, str(data.get("error", ""))[:50])
    session_id = data.get("session_id") or data.get("id")
    if not session_id:
        return

    for _ in range(15):
        st, st_data = api("GET", f"/api/labs/{session_id}/status/", token=token)
        if st == 200 and st_data.get("status") in ("RUNNING", "COMPLETED", "FAILED", "TERMINATED"):
            break
        import time
        time.sleep(2)

    _batch(s, "LabRunner", [
        ("GET", f"/api/labs/{session_id}/status/", None, (200,), "status tab"),
        ("GET", f"/api/labs/{session_id}/hints/", None, (200,), "hints GET"),
        ("GET", f"/api/labs/{session_id}/commands/", None, (200,), "commands/replay tab"),
        ("GET", f"/api/labs/{session_id}/replay/", None, (200,), "replay data"),
    ], token)

    st, _ = api("POST", f"/api/labs/{session_id}/hints/", token=token)
    s.record("Lab hints POST reveal", st in (200, 400), st)

    st, _ = api("POST", f"/api/labs/{session_id}/validate/", token=token, data={})
    s.record("Lab validate/check solution", st in (200, 400), st)

    st, _ = api("GET", f"/api/labs/{session_id}/solution/", token=token)
    s.record("Lab solution endpoint", st in (200, 403, 404), st)

    st, _ = api("POST", f"/api/labs/{session_id}/stop/", token=token)
    s.record("Lab stop", st in (200, 204), st)


def run_admin_all_tabs(s, admin_token: str):
    print("\n=== [Admin] All tabs & options ===")
    admin_cases = [
        ("GET", "/api/admin/overview/", None, (200,), "overview tab"),
        ("GET", "/api/admin/health/", None, (200,), "health panel"),
        ("GET", "/api/admin/analytics/?days=7", None, (200,), "analytics tab"),
        ("GET", "/api/admin/analytics/?days=30", None, (200,), "analytics 30d"),
        ("GET", "/api/admin/activity/", None, (200,), "activity feed"),
        ("GET", "/api/admin/audit-logs/", None, (200,), "audit logs"),
        ("GET", "/api/admin/config/", None, (200,), "settings config"),
        ("GET", "/api/admin/maintenance/", None, (200,), "maintenance GET"),
        ("GET", "/api/admin/scenarios/", None, (200,), "scenarios tab"),
        ("GET", "/api/admin/technologies/", None, (200,), "technologies tab"),
        ("GET", "/api/admin/tags/", None, (200,), "tags tab"),
        ("GET", "/api/admin/users/", None, (200,), "users tab"),
        ("GET", "/api/admin/users/inactive/?days=90", None, (200,), "inactive users"),
        ("GET", "/api/admin/labs/active/", None, (200,), "active labs tab"),
        ("GET", "/api/admin/subscriptions/", None, (200,), "subscriptions tab"),
        ("GET", "/api/admin/threads/", None, (200,), "threads tab"),
        ("GET", "/api/admin/jira/tickets/", None, (200,), "jira tab cached"),
        ("GET", "/api/admin/jira/tickets/?sync=1", None, (200,), "jira sync refresh"),
        ("GET", "/api/admin/export/users/", None, (200,), "export users CSV"),
        ("GET", "/api/admin/export/labs/", None, (200,), "export labs CSV"),
        ("GET", "/api/admin/export/progress/", None, (200,), "export progress CSV"),
        ("GET", "/api/billing/subscription-logs/", None, (200,), "billing logs"),
    ]
    _batch(s, "Admin", admin_cases, admin_token)

    st, users = api("GET", "/api/admin/users/?limit=5", token=admin_token)
    if st == 200 and isinstance(users, list) and users:
        uid = users[0].get("id")
        st, _ = api("GET", f"/api/admin/users/{uid}/", token=admin_token)
        s.record("Admin user detail modal", st == 200, st)

    st, scenarios = api("GET", "/api/admin/scenarios/", token=admin_token)
    if st == 200 and isinstance(scenarios, list) and scenarios:
        pk = scenarios[0].get("id")
        st, _ = api("GET", f"/api/admin/scenarios/{pk}/", token=admin_token)
        s.record("Admin scenario detail", st in (200, 404), st)

    st, threads = api("GET", "/api/admin/threads/", token=admin_token)
    thread_list = threads if isinstance(threads, list) else (threads.get("results") if isinstance(threads, dict) else [])
    if thread_list:
        tid = thread_list[0].get("id")
        st, _ = api("GET", f"/api/admin/threads/{tid}/", token=admin_token)
        s.record("Admin thread detail modal", st == 200, st)

    st, _ = api("POST", "/api/admin/labs/terminate-idle/", token=admin_token, data={})
    s.record("Admin terminate idle labs", st in (200, 204), st)


def run_technology_all_scenarios(s, token: str):
    """Every technology: at least one scenario Jira + optional lab start."""
    if os.environ.get("E2E_SKIP_DUPLICATE_LABS") == "1":
        return
    if SKIP_LAB:
        return
    print("\n=== [Tab] All technologies → scenarios → Jira ===")
    st, techs = api("GET", "/api/technologies/", token=token)
    if st != 200 or not techs:
        s.record("All-tech scan", False, st)
        return
    items = techs if isinstance(techs, list) else techs
    for tech in items:
        slug = tech.get("slug", "")
        st, detail = api("GET", f"/api/scenarios/?technology_slug={slug}&limit=3", token=token)
        if st != 200:
            s.record(f"Tech {slug} scenarios", False, st)
            continue
        sc_items = detail if isinstance(detail, list) else detail.get("results", detail) or []
        if not sc_items:
            s.record(f"Tech {slug} scenarios", True, detail="empty")
            continue
        sc = sc_items[0]
        sid = sc.get("id")
        st_j, jira = api("POST", f"/api/jira/tickets/scenario/{sid}/", token=token)
        key = (jira.get("ticket") or {}).get("issue_key", "")
        s.record(f"Tech {slug} jira", st_j in (200, 201) and bool(key), st_j, key[:15] or "no key")


def run_full_ui_coverage(s, token: str, email: str, password: str, refresh: str = "") -> str:
    """Run every tab/feature test. Returns (possibly refreshed) token."""
    print("\n" + "=" * 60)
    print("FULL UI / TAB / FEATURE COVERAGE")
    print("=" * 60)

    if grant_test_subscriptions(email):
        s.record("Grant all tech subscriptions", True)

    run_search_and_public_extras(s)
    run_dashboard_tab(s, token)
    run_technologies_tab(s, token)
    scenario = run_scenarios_tab(s, token)
    run_leaderboard_tab(s, token)
    run_bookmarks_tab(s, token)
    run_lab_history_tab(s, token)
    run_achievements_tab(s, token)
    run_profile_tab(s, token)
    run_notifications_tab(s, token)
    run_billing_all_options(s, token)
    run_billing_subscribe_cancel_user(s, token)
    run_community_full(s, token)
    run_lab_runner_all_tabs(s, token, scenario)
    run_technology_all_scenarios(s, token)
    run_question_bank_api(s, token)
    run_frontend_static_pages(s)
    run_forgot_password(s, email)

    test_user_id = None
    scenario_id = scenario.get("id") if scenario else None
    try:
        import django
        import sys
        sys.path.insert(0, "/app")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        django.setup()
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.filter(email=email).first()
        if u:
            test_user_id = u.id
    except Exception:
        pass

    if os.environ.get("SUPERUSER_EMAIL") and os.environ.get("SUPERUSER_PASSWORD"):
        admin_token, _ = login(os.environ["SUPERUSER_EMAIL"], os.environ["SUPERUSER_PASSWORD"])
        if admin_token:
            run_admin_all_tabs(s, admin_token)
            run_admin_write_ops(s, admin_token, test_user_id, scenario_id)
            _run_community_admin_mod(s, admin_token, token)

    token = run_auth_token_flow(s, token, email, password, refresh) or token

    print("\n=== Coverage manifest (all tabs & features) ===")
    total_features = sum(len(v) for v in UI_COVERAGE.values())
    print(f"  Areas: {len(UI_COVERAGE)} | Feature checks defined: {total_features}")
    for area, features in UI_COVERAGE.items():
        print(f"  • {area}: {', '.join(features)}")

    return token
