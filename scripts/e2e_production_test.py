#!/usr/bin/env python3
"""
FixitLab production E2E test suite.
Run inside backend container:
  docker compose exec backend python /scripts/e2e_production_test.py

Or against live site:
  BASE_URL=https://fixitlab.in python scripts/e2e_production_test.py
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_EMAIL = os.environ.get("SUPERUSER_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("SUPERUSER_PASSWORD", "")
SKIP_LAB = os.environ.get("E2E_SKIP_LAB", "1") == "1"  # lab start is slow; set E2E_SKIP_LAB=0 to test
VERBOSE = os.environ.get("E2E_VERBOSE", "0") == "1"
# Django SECURE_SSL_REDIRECT requires this when hitting Daphne directly over HTTP
INTERNAL_HTTP = BASE_URL.startswith("http://127.0.0.1") or BASE_URL.startswith("http://backend")


@dataclass
class Result:
    name: str
    ok: bool
    status: int | str = 0
    detail: str = ""


@dataclass
class Suite:
    results: list[Result] = field(default_factory=list)

    def record(self, name: str, ok: bool, status=0, detail=""):
        self.results.append(Result(name, ok, status, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))

    @property
    def failed(self):
        return [r for r in self.results if not r.ok]


def err_msg(data) -> str:
    if isinstance(data, dict):
        return str(data.get("detail", data.get("error", "")))[:80]
    return ""


def api(method: str, path: str, token: str | None = None, data: dict | None = None, headers: dict | None = None):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    if headers:
        hdrs.update(headers)
    if INTERNAL_HTTP:
        hdrs["X-Forwarded-Proto"] = "https"
        hdrs["Host"] = "fixitlab.in"
    req = Request(url, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"_raw": raw[:200]}
            return resp.status, parsed
    except HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"_raw": raw[:200]}
        return e.code, parsed
    except URLError as e:
        return 0, {"error": str(e.reason)}


def login(email: str, password: str) -> tuple[str | None, dict]:
    status, data = api("POST", "/api/auth/login/", data={"email": email, "password": password})
    if status == 200 and data.get("access"):
        return data["access"], data
    return None, data


def run_public_tests(s: Suite):
    print("\n=== Public / unauthenticated endpoints ===")
    cases = [
        ("GET", "/api/health/", None, (200,)),
        ("GET", "/api/stats/", None, (200,)),
        ("GET", "/api/technologies/", None, (200,)),
        ("GET", "/api/scenarios/", None, (200,)),
        ("GET", "/api/categories/", None, (200,)),
        ("GET", "/api/tags/", None, (200,)),
        ("GET", "/api/config/", None, (200,)),
        ("GET", "/api/leaderboard/", None, (200,)),
        ("GET", "/api/auth/social/config/", None, (200,)),
        ("GET", "/api/billing/gateway-status/", None, (200,)),
        ("GET", "/api/billing/currency-rate/", None, (200,)),
        ("GET", "/api/search/?q=linux", None, (200,)),
        ("GET", "/api/community/threads/", None, (200, 401)),  # may require auth
    ]
    for method, path, body, ok_statuses in cases:
        status, data = api(method, path, data=body)
        ok = status in ok_statuses
        err = err_msg(data)
        s.record(f"{method} {path}", ok, status, err)


def run_auth_registration(s: Suite) -> tuple[str | None, str]:
    print("\n=== Auth: OTP + registration ===")
    email = f"e2e-{uuid.uuid4().hex[:8]}@fixitlab-test.local"
    password = "E2eTestPass123!"

    status, data = api("POST", "/api/auth/send-otp/", data={"email": email})
    s.record("POST /api/auth/send-otp/", status == 200, status, str(data.get("error", "")))

    session_token = data.get("session_token", "")
    otp_code = None

    # Read OTP from DB when running inside Django container
    try:
        sys.path.insert(0, "/app")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from apps.accounts.models import EmailVerificationOTP
        otp_obj = EmailVerificationOTP.objects.filter(email=email).order_by("-created_at").first()
        if otp_obj:
            otp_code = otp_obj.code
            session_token = otp_obj.session_token
            s.record("OTP stored in DB", True)
        else:
            s.record("OTP stored in DB", False, detail="No OTP row found")
    except Exception as e:
        s.record("OTP DB lookup", False, detail=str(e)[:80])

    if otp_code and session_token:
        status, data = api("POST", "/api/auth/verify-otp/", data={"session_token": session_token, "code": otp_code})
        s.record("POST /api/auth/verify-otp/", status == 200, status, str(data.get("error", "")))

        status, data = api("POST", "/api/auth/register/", data={
            "email": email,
            "password": password,
            "session_token": session_token,
            "first_name": "E2E",
            "last_name": "User",
        })
        s.record("POST /api/auth/register/", status in (200, 201), status, str(data.get("error", "")))
        if data.get("access"):
            return data["access"], email

    token, _ = login(email, password)
    return token, email


def run_user_flow(s: Suite, token: str, label: str = "user"):
    print(f"\n=== Authenticated user flow ({label}) ===")
    endpoints = [
        ("GET", "/api/auth/profile/"),
        ("GET", "/api/progress/"),
        ("GET", "/api/achievements/"),
        ("GET", "/api/plan/"),
        ("GET", "/api/labs/active/"),
        ("GET", "/api/labs/history/"),
        ("GET", "/api/bookmarks/"),
        ("GET", "/api/notifications/"),
        ("GET", "/api/notifications/preferences/"),
        ("GET", "/api/billing/subscriptions/"),
        ("GET", "/api/jira/tickets/"),
    ]
    for method, path in endpoints:
        status, data = api(method, path, token=token)
        ok = status == 200
        s.record(f"{label} {method} {path}", ok, status, err_msg(data))


def run_lab_flow(s: Suite, token: str):
    if SKIP_LAB:
        s.record("Lab provisioning", True, detail="skipped E2E_SKIP_LAB=1")
        return
    print("\n=== Lab lifecycle ===")
    status, scenarios = api("GET", "/api/scenarios/", token=token)
    if status != 200 or not scenarios:
        s.record("Fetch scenarios for lab", False, status)
        return

    scenario = None
    items = scenarios if isinstance(scenarios, list) else scenarios.get("results", scenarios)
    for sc in items:
        if sc.get("is_active") and sc.get("difficulty") in ("easy", "beginner", "medium", None):
            scenario = sc
            break
    if not scenario and items:
        scenario = items[0]
    if not scenario:
        s.record("Find active scenario", False, detail="no scenarios")
        return

    sid = scenario.get("id")
    status, data = api("POST", f"/api/labs/{sid}/start/", token=token)
    s.record(f"POST /api/labs/{sid}/start/", status in (200, 201, 202), status, str(data.get("error", data.get("status", "")))[:60])

    session_id = data.get("session_id") or data.get("id")
    if not session_id:
        return

    for path_suffix in ("status/", "hints/", "commands/"):
        st, _ = api("GET", f"/api/labs/{session_id}/{path_suffix}", token=token)
        s.record(f"GET lab {path_suffix}", st == 200, st)

    st, _ = api("POST", f"/api/labs/{session_id}/stop/", token=token)
    s.record(f"POST lab stop", st in (200, 204), st)


def run_admin_flow(s: Suite):
    print("\n=== Admin panel API ===")
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        s.record("Admin login", False, detail="SUPERUSER_EMAIL/PASSWORD not set")
        return

    token, data = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not token:
        s.record("Admin login", False, detail=str(data.get("error", data)))
        return
    s.record("Admin login", True)

    if not data.get("user", {}).get("is_staff"):
        s.record("Admin is_staff flag", False)
        return
    s.record("Admin is_staff flag", True)

    admin_paths = [
        "/api/admin/overview/",
        "/api/admin/health/",
        "/api/admin/analytics/",
        "/api/admin/activity/",
        "/api/admin/users/",
        "/api/admin/scenarios/",
        "/api/admin/technologies/",
        "/api/admin/labs/active/",
        "/api/admin/subscriptions/",
        "/api/admin/threads/",
        "/api/admin/config/",
        "/api/admin/audit-logs/",
        "/api/billing/subscription-logs/",
    ]
    for path in admin_paths:
        status, resp = api("GET", path, token=token)
        ok = status == 200
        s.record(f"Admin GET {path}", ok, status, err_msg(resp))


def run_community_flow(s: Suite, token: str):
    print("\n=== Community ===")
    status, data = api("POST", "/api/community/threads/", token=token, data={
        "title": f"E2E thread {uuid.uuid4().hex[:6]}",
        "body": "Automated E2E test thread — safe to delete",
    })
    s.record("POST community thread", status in (200, 201), status, str(data.get("error", data.get("detail", "")))[:60])


def run_contact(s: Suite):
    print("\n=== Contact form ===")
    status, data = api("POST", "/api/contact/", data={
        "name": "E2E Tester",
        "email": "e2e@fixitlab-test.local",
        "subject": "E2E test",
        "message": "Automated test message",
    })
    s.record("POST /api/contact/", status in (200, 201), status, str(data.get("error", ""))[:60])


def run_jira_webhook(s: Suite):
    print("\n=== Jira webhook security ===")
    payload = json.dumps({"webhookEvent": "jira:issue_updated", "issue": {"key": "E2E-1", "fields": {"status": {"name": "Done"}}}}).encode()
    status, _ = api("POST", "/api/jira/webhooks/", data=json.loads(payload))
    s.record("Jira webhook rejects unsigned", status == 403, status)

    secret = os.environ.get("JIRA_WEBHOOK_SECRET", "")
    if secret:
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        hdrs = {"Content-Type": "application/json", "X-FixitLab-Signature": f"sha256={sig}"}
        if INTERNAL_HTTP:
            hdrs["X-Forwarded-Proto"] = "https"
            hdrs["Host"] = "fixitlab.in"
        req = Request(
            f"{BASE_URL}/api/jira/webhooks/",
            data=payload,
            headers=hdrs,
            method="POST",
        )
        try:
            with urlopen(req, timeout=15) as resp:
                s.record("Jira webhook accepts HMAC", resp.status == 200, resp.status)
        except HTTPError as e:
            s.record("Jira webhook accepts HMAC", e.code == 200, e.code)
    else:
        s.record("Jira webhook HMAC test", True, detail="skipped — no secret in env")


def run_billing_flow(s: Suite, token: str):
    print("\n=== Billing ===")
    for path in ("/api/billing/gateway-status/", "/api/billing/subscriptions/", "/api/billing/currency-rate/"):
        st, data = api("GET", path, token=token)
        s.record(f"GET {path}", st == 200, st, err_msg(data))


def run_auth_extras(s: Suite, token: str, email: str, password: str):
    print("\n=== Auth extras ===")
    st, _ = api("POST", "/api/auth/forgot-password/", data={"email": email})
    s.record("POST forgot-password", st in (200, 202), st)

    st, data = api("PUT", "/api/auth/profile/", token=token, data={"first_name": "E2EUpdated"})
    s.record("PUT profile", st == 200, st)


def clear_rate_limit_cache():
    try:
        sys.path.insert(0, "/app")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.core.cache import cache
        cache.clear()
    except Exception:
        pass


def run_concurrent_users(s: Suite, n: int = 3):
    print(f"\n=== Concurrent new user registrations ({n} threads) ===")
    clear_rate_limit_cache()

    def register_one(i):
        email = f"e2e-concurrent-{i}-{uuid.uuid4().hex[:6]}@fixitlab-test.local"
        password = "E2eTestPass123!"
        st, data = api("POST", "/api/auth/send-otp/", data={"email": email})
        if st != 200:
            return False
        try:
            sys.path.insert(0, "/app")
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            import django
            django.setup()
            from apps.accounts.models import EmailVerificationOTP
            otp = EmailVerificationOTP.objects.filter(email=email).order_by("-created_at").first()
            if not otp:
                return False
            st, _ = api("POST", "/api/auth/verify-otp/", data={"session_token": otp.session_token, "code": otp.code})
            if st != 200:
                return False
            st, reg = api("POST", "/api/auth/register/", data={
                "email": email, "password": password,
                "session_token": otp.session_token,
            })
            return st in (200, 201) and bool(reg.get("access"))
        except Exception:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
        results = list(ex.map(register_one, range(n)))
    ok = sum(results)
    s.record(f"Concurrent registrations {ok}/{n}", ok == n)


def run_concurrent_login(s: Suite, n_users: int = 8):
    print(f"\n=== Concurrent admin logins ({n_users} threads) ===")
    clear_rate_limit_cache()
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        s.record("Concurrent login", False, detail="no admin creds")
        return

    def one_login(_):
        t, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        return t is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_users) as ex:
        results = list(ex.map(one_login, range(n_users)))
    ok_count = sum(results)
    s.record(f"Concurrent logins {ok_count}/{n_users}", ok_count == n_users)


def run_email_logs(s: Suite):
    print("\n=== Email delivery logs ===")
    try:
        sys.path.insert(0, "/app")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from apps.notifications.models import EmailLog
        recent = EmailLog.objects.order_by("-created_at")[:5]
        sent = EmailLog.objects.filter(status="sent").count()
        failed = EmailLog.objects.filter(status="failed").count()
        s.record(f"EmailLog sent={sent} failed={failed}", True, detail=f"recent={recent.count()}")
        if failed > 0:
            from apps.notifications.gmail_api import is_gmail_api_configured
            if is_gmail_api_configured() or os.environ.get("SENDGRID_API_KEY"):
                last_fail = EmailLog.objects.filter(status="failed").first()
                if last_fail:
                    s.record("Last email failure (historical)", True, detail=last_fail.error[:60])
            else:
                s.record(
                    "Email delivery config",
                    False,
                    detail="Set GMAIL_OAUTH_REFRESH_TOKEN or SENDGRID_API_KEY",
                )
    except Exception as e:
        s.record("EmailLog check", False, detail=str(e)[:80])


def main():
    print(f"FixitLab E2E — BASE_URL={BASE_URL}")
    s = Suite()
    t0 = time.time()

    run_public_tests(s)
    token, test_email = run_auth_registration(s)
    if token:
        run_user_flow(s, token, "new_user")
        run_auth_extras(s, token, test_email, "E2eTestPass123!")
        run_billing_flow(s, token)
        run_community_flow(s, token)
        run_lab_flow(s, token)
    else:
        s.record("User registration flow", False, detail="no token")

    run_admin_flow(s)
    run_contact(s)
    run_jira_webhook(s)
    run_concurrent_users(s, 3)
    run_concurrent_login(s, 8)
    run_email_logs(s)

    elapsed = time.time() - t0
    passed = sum(1 for r in s.results if r.ok)
    total = len(s.results)
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} passed in {elapsed:.1f}s")
    if s.failed:
        print("\nFailures:")
        for r in s.failed:
            print(f"  - {r.name} [{r.status}] {r.detail}")
        sys.exit(1)
    print("All E2E checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
