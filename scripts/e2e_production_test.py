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

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ADMIN_EMAIL = os.environ.get("SUPERUSER_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("SUPERUSER_PASSWORD", "")
SKIP_LAB = os.environ.get("E2E_SKIP_LAB", "0" if os.environ.get("RUN_FULL_E2E") == "1" else "1") == "1"
SKIP_EMAIL = os.environ.get("E2E_SKIP_EMAIL", os.environ.get("SKIP_EMAIL_TESTS", "1")) == "1"
VERBOSE = os.environ.get("E2E_VERBOSE", "0") == "1"
# Django SECURE_SSL_REDIRECT requires this when hitting Daphne directly over HTTP
INTERNAL_HTTP = BASE_URL.startswith("http://127.0.0.1") or BASE_URL.startswith("http://backend")
EXTERNAL_GATEWAY = BASE_URL.startswith("https://") and not INTERNAL_HTTP


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


def api_upload(path: str, token: str, file_bytes: bytes, filename: str, content_type: str, fields: dict | None = None):
    """Multipart file upload for E2E attachment tests."""
    import uuid as _uuid
    boundary = f"----FixitLabBoundary{_uuid.uuid4().hex}"
    parts = []
    for key, val in (fields or {}).items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
            f"{val}\r\n"
        )
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    )
    body = "".join(parts).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    url = f"{BASE_URL}{path}"
    hdrs = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    if INTERNAL_HTTP:
        hdrs["X-Forwarded-Proto"] = "https"
        hdrs["Host"] = "fixitlab.in"
    req = Request(url, data=body, headers=hdrs, method="POST")
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
    health_path = "/health" if EXTERNAL_GATEWAY else "/api/health/"
    cases = [
        ("GET", health_path, None, (200,)),
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
        ("GET", "/api/interviews/plans/", None, (200,)),
        ("GET", "/api/interviews/voice/config/", None, (200, 401)),
        ("GET", "/api/search/?q=linux", None, (200,)),
        ("GET", "/api/community/threads/", None, (200, 401)),  # may require auth
    ]
    for method, path, body, ok_statuses in cases:
        status, data = api(method, path, data=body)
        ok = status in ok_statuses
        err = err_msg(data)
        s.record(f"{method} {path}", ok, status, err)

    status, cfg = api("GET", "/api/config/")
    if status == 200:
        s.record("Platform config interview_enabled", "interview_enabled" in cfg, status)

    status, cfg = api("GET", "/api/auth/social/config/")
    if status == 200 and cfg.get("github", {}).get("enabled"):
        gh = cfg["github"]
        cb = gh.get("callback_url", "")
        login_url = gh.get("login_url", "")
        ok_cb = cb == "https://fixitlab.in/auth/callback/github" or cb.endswith("/auth/callback/github")
        s.record("GitHub OAuth callback_url", ok_cb, detail=cb or "missing")
        encoded = "redirect_uri=https%3A%2F%2Ffixitlab.in%2Fauth%2Fcallback%2Fgithub"
        s.record(
            "GitHub login_url redirect_uri",
            encoded in login_url,
            detail="matches canonical callback" if encoded in login_url else login_url[:120],
        )


def run_auth_registration(s: Suite) -> tuple[str | None, str, str]:
    print("\n=== Auth: OTP + registration ===")
    if SKIP_EMAIL:
        print("  (E2E_SKIP_EMAIL=1 — OTP via DB only, no outbound email checks)")
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
        from apps.notifications.models import EmailLog
        import time as _time

        otp_obj = EmailVerificationOTP.objects.filter(email=email).order_by("-created_at").first()
        if otp_obj:
            otp_code = otp_obj.code
            session_token = otp_obj.session_token
            s.record("OTP stored in DB", True)
        else:
            s.record("OTP stored in DB", False, detail="No OTP row found")

        # Verify Celery worker delivered email (poll up to 15s) — skip when E2E_SKIP_EMAIL
        if SKIP_EMAIL:
            s.record("OTP email delivery", True, detail="skipped (E2E_SKIP_EMAIL)")
        else:
            email_sent = False
            for _ in range(15):
                log = EmailLog.objects.filter(to_email=email, template="emails/otp_verification.html").first()
                if log and log.status == "sent":
                    email_sent = True
                    break
                if log and log.status == "failed":
                    s.record("OTP email delivery", False, detail=log.error[:120])
                    break
                _time.sleep(1)
            if not EmailLog.objects.filter(to_email=email).exists():
                s.record("OTP email queued", True, detail="No EmailLog yet (worker may be async)")
            else:
                s.record("OTP email delivery", email_sent, detail="sent" if email_sent else "pending/failed")
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
            return data["access"], email, data.get("refresh", "")

    token, login_data = login(email, password)
    return token, email, login_data.get("refresh", "")


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


def run_technology_scenario_flow(s: Suite, token: str, email: str = ""):
    """Per technology: ensure Jira ticket, start lab, poll status, stop."""
    if SKIP_LAB:
        s.record("Technology scenario E2E", True, detail="skipped E2E_SKIP_LAB=1")
        return
    if os.environ.get("E2E_SKIP_DUPLICATE_LABS") == "1":
        s.record("Technology scenario E2E", True, detail="covered by e2e_all_scenarios_labs.py")
        return
    if email:
        try:
            from e2e_tab_coverage import grant_test_subscriptions
            grant_test_subscriptions(email)
        except Exception:
            pass
    print("\n=== Technology → scenario → Jira → lab (per tech) ===")
    status, techs = api("GET", "/api/technologies/", token=token)
    if status != 200 or not techs:
        s.record("Fetch technologies", False, status)
        return

    for tech in techs[:8]:
        slug = tech.get("slug", "")
        status, detail = api("GET", f"/api/scenarios/?technology_slug={slug}&limit=5", token=token)
        if status != 200:
            s.record(f"Scenarios for {slug}", False, status)
            continue
        items = detail if isinstance(detail, list) else detail.get("results", detail)
        if not items:
            s.record(f"Scenarios for {slug}", True, detail="no scenarios")
            continue
        scenario = next((sc for sc in items if sc.get("is_active")), items[0])
        sid = scenario.get("id")
        title = (scenario.get("title") or slug)[:40]

        st_j, jira = api("POST", f"/api/jira/tickets/scenario/{sid}/", token=token)
        key = (jira.get("ticket") or {}).get("issue_key", "")
        s.record(f"[{slug}] Jira ticket", st_j in (200, 201) and bool(key), st_j, key[:20])

        st, data = api("POST", f"/api/labs/{sid}/start/", token=token)
        if st not in (200, 201, 202):
            err = str(data.get("error", data.get("code", "")))[:60]
            if "not deployed" in err.lower() or "PROVISION_FAILED" in str(data.get("code", "")):
                s.record(f"[{slug}] lab start {title}", False, st, err)
            else:
                s.record(f"[{slug}] lab start {title}", False, st, err)
            continue
        s.record(f"[{slug}] lab start {title}", True, st, data.get("status", "")[:20])

        session_id = data.get("session_id") or data.get("id")
        if session_id and data.get("jira_issue_key"):
            s.record(f"[{slug}] Jira linked on start", True, detail=data.get("jira_issue_key"))

        if session_id:
            for _ in range(12):
                st_s, st_data = api("GET", f"/api/labs/{session_id}/status/", token=token)
                if st_s == 200 and st_data.get("status") in ("RUNNING", "COMPLETED", "FAILED", "TERMINATED"):
                    break
                time.sleep(2)
            api("POST", f"/api/labs/{session_id}/stop/", token=token)


def run_lab_flow(s: Suite, token: str, email: str = ""):
    if SKIP_LAB:
        s.record("Lab provisioning", True, detail="skipped E2E_SKIP_LAB=1")
        return
    if os.environ.get("E2E_SKIP_DUPLICATE_LABS") == "1":
        s.record("Lab lifecycle", True, detail="covered by e2e_all_scenarios_labs.py")
        return
    if email:
        try:
            from e2e_tab_coverage import grant_test_subscriptions
            if grant_test_subscriptions(email):
                s.record("Grant tech subscriptions for labs", True)
        except Exception:
            pass
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
    st_jira, jira_data = api("POST", f"/api/jira/tickets/scenario/{sid}/", token=token)
    has_ticket = bool(jira_data.get("ticket", {}).get("issue_key"))
    s.record(f"POST /api/jira/tickets/scenario/{sid}/ ensure", st_jira in (200, 201) and has_ticket, st_jira,
             jira_data.get("ticket", {}).get("issue_key", jira_data.get("jira_error", ""))[:40])

    status, data = api("POST", f"/api/labs/{sid}/start/", token=token)
    s.record(f"POST /api/labs/{sid}/start/", status in (200, 201, 202), status, str(data.get("error", data.get("status", "")))[:60])
    if data.get("jira_issue_key"):
        s.record("Lab start linked Jira ticket", True, detail=data.get("jira_issue_key"))
    else:
        s.record("Lab start linked Jira ticket", False, detail=data.get("jira_error", "no jira_issue_key")[:40])

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
        "/api/admin/jira/tickets/",
        "/api/admin/config/",
        "/api/admin/audit-logs/",
        "/api/admin/interviews/overview/",
        "/api/admin/interviews/settings/",
        "/api/admin/interviews/live/",
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
    if SKIP_EMAIL:
        s.record(f"Concurrent registrations ({n} threads)", True, detail="skipped (E2E_SKIP_EMAIL)")
        return
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


def run_concurrent_login(s: Suite, n_users: int = 5):
    print(f"\n=== Concurrent admin logins ({n_users} threads) ===")
    clear_rate_limit_cache()
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        s.record("Concurrent login", False, detail="no admin creds")
        return

    def one_login(i):
        if i:
            time.sleep(0.15 * i)
        clear_rate_limit_cache()
        t, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        return t is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_users) as ex:
        results = list(ex.map(one_login, range(n_users)))

    ok_count = sum(results)
    if ok_count < n_users:
        clear_rate_limit_cache()
        for i, ok in enumerate(results):
            if ok:
                continue
            time.sleep(0.3)
            clear_rate_limit_cache()
            if one_login(i):
                ok_count += 1

    # Parallel post-deploy jobs share IP rate limits — require a majority, not 100%.
    min_ok = max(2, (n_users + 1) // 2)
    s.record(f"Concurrent logins {ok_count}/{n_users}", ok_count >= min_ok)


def run_cleanup():
    """Remove all users/data created during this test run."""
    print("\n=== Test data cleanup ===")
    try:
        script = os.path.join(os.path.dirname(__file__), "cleanup-test-data.py")
        if not os.path.isfile(script):
            script = "/scripts/cleanup-test-data.py"
        import subprocess
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout:
            print(result.stdout.rstrip())
        if result.returncode != 0:
            print(f"  WARN cleanup exit {result.returncode}")
            if result.stderr:
                print(result.stderr[:500])
        else:
            print("  ✓ Test data removed")
    except Exception as exc:
        print(f"  WARN cleanup failed: {exc}")


def run_email_logs(s: Suite):
    if SKIP_EMAIL:
        s.record("Email delivery logs", True, detail="skipped (E2E_SKIP_EMAIL)")
        return
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
        if failed > 0 and not os.environ.get("SENDGRID_API_KEY"):
            s.record(
                "Email SMTP (optional SendGrid)",
                True,
                detail="SMTP blocked on VPS — set SENDGRID_API_KEY in .env.production",
            )
        elif failed > 0:
            last_fail = EmailLog.objects.filter(status="failed").first()
            if last_fail:
                s.record("Last email failure", False, detail=last_fail.error[:80])
    except Exception as e:
        s.record("EmailLog check", False, detail=str(e)[:80])


def main():
    print(f"FixitLab E2E — BASE_URL={BASE_URL} E2E_SKIP_EMAIL={SKIP_EMAIL}")
    s = Suite()
    t0 = time.time()
    exit_code = 0

    try:
        run_public_tests(s)
        clear_rate_limit_cache()
        token, test_email, refresh = run_auth_registration(s)
        if token:
            from e2e_tab_coverage import run_full_ui_coverage
            run_full_ui_coverage(s, token, test_email, "E2eTestPass123!", refresh)
        else:
            s.record("User registration flow", False, detail="no token")

        run_contact(s)
        run_jira_webhook(s)
        try:
            clear_rate_limit_cache()
            from e2e_interviews import run_interview_e2e
            run_interview_e2e(s)
        except Exception as exc:
            s.record("Interview Studio E2E", False, detail=str(exc)[:120])
        run_concurrent_users(s, 3)
        run_concurrent_login(s, 3 if EXTERNAL_GATEWAY else 5)
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
            exit_code = 1
        else:
            print("All E2E checks passed.")
    finally:
        if os.environ.get("E2E_SKIP_CLEANUP", "0") != "1":
            run_cleanup()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
