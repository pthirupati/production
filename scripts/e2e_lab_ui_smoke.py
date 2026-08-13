#!/usr/bin/env python3
"""
Lab UI smoke — catches frontend render crashes (e.g. TDZ / ErrorBoundary).

Starts a lab via API, loads /lab/{id} in Playwright, fails if:
  - "Something went wrong" appears
  - "Cannot access" (minified init error) appears
  - ErrorBoundary retry UI without terminal chrome

Env:
  SITE_URL=https://fixitlab.in
  E2E_SKIP_LAB=1 — skip
  E2E_LAB_UI_SCENARIOS=3 — number of scenarios to spot-check (default 3)
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from urllib.request import Request, urlopen

SITE_URL = os.environ.get("SITE_URL", "https://fixitlab.in").rstrip("/")
API = f"{SITE_URL}/api"
SKIP = os.environ.get("E2E_SKIP_LAB", "0") == "1"
MAX_SCENARIOS = int(os.environ.get("E2E_LAB_UI_SCENARIOS", "3"))

passed = 0
failed = 0
errors: list[str] = []


def record(name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        msg = f"{name}" + (f" — {detail}" if detail else "")
        errors.append(msg)
        print(f"  [FAIL] {msg}")


def api_get(path: str, token: str | None = None):
    hdrs = {"Accept": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    req = Request(f"{API}{path}", headers=hdrs)
    with urlopen(req, timeout=60) as resp:
        return resp.status, json.loads(resp.read().decode() or "{}")


def api_post(path: str, data: dict | None = None, token: str | None = None):
    body = json.dumps(data or {}).encode()
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    req = Request(f"{API}{path}", data=body, headers=hdrs, method="POST")
    with urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read().decode() or "{}")


def _setup_user_token() -> str | None:
    sys.path.insert(0, "/app")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import RefreshToken
    from apps.accounts.models import EmailVerificationOTP

    email = f"e2e-lab-ui-{uuid.uuid4().hex[:8]}@fixitlab-test.local"
    password = "E2eLabUi123!"
    try:
        st, _ = api_post("/auth/send-otp/", {"email": email})
        if st != 200:
            return None
        otp = EmailVerificationOTP.objects.filter(email=email).order_by("-created_at").first()
        if not otp:
            return None
        code = EmailVerificationOTP.e2e_peek_code(otp.session_token)
        if not code:
            return None
        api_post("/auth/verify-otp/", {"session_token": otp.session_token, "code": code})
        st, reg = api_post("/auth/register/", {
            "email": email,
            "password": password,
            "username": f"e2e_lab_ui_{uuid.uuid4().hex[:6]}",
            "session_token": otp.session_token,
            "accepted_legal": True,
        })
        if st not in (200, 201):
            return None
        user = get_user_model().objects.filter(email=email).first()
        if not user:
            return None
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    except Exception as exc:
        print(f"  WARN: user setup failed: {exc}")
        return None


def _wait_running(token: str, session_id: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        st, data = api_get(f"/labs/{session_id}/status/", token)
        if st == 200 and data.get("status") == "RUNNING":
            return True
        if st == 200 and data.get("status") in ("FAILED", "TERMINATED", "EXPIRED"):
            return False
        time.sleep(3)
    return False


def _check_lab_page(page, session_id: str, label: str) -> None:
    url = f"{SITE_URL}/lab/{session_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    body = page.inner_text("body")
    bad_phrases = (
        "Something went wrong",
        "Cannot access",
        "before initialization",
        "An unexpected error occurred",
    )
    for phrase in bad_phrases:
        if phrase in body:
            record(f"Lab UI {label}", False, f"page contains '{phrase}'")
            return
    # Terminal mount or lab chrome should appear for RUNNING sessions
    has_lab = (
        page.locator(".xterm").count() > 0
        or page.get_by_text("Check Solution").count() > 0
        or page.get_by_text("Hints").count() > 0
        or page.get_by_text("Lab time").count() > 0
        or page.get_by_text("Instructions").count() > 0
    )
    record(f"Lab UI {label}", has_lab, "no lab chrome detected" if not has_lab else "")


def main() -> int:
    if SKIP:
        print("Lab UI smoke skipped (E2E_SKIP_LAB=1)")
        return 0

    print(f"Lab UI smoke — {SITE_URL} (up to {MAX_SCENARIOS} scenarios)")

    token = _setup_user_token()
    if not token:
        record("Auth for lab UI", False, "could not create test user")
        return 1

    st, scenarios = api_get("/scenarios/?limit=50", token)
    items = scenarios if isinstance(scenarios, list) else (scenarios.get("results") or [])
    deployable = [s for s in items if s.get("is_active") and s.get("has_docker_image")]
    if not deployable:
        deployable = [s for s in items if s.get("is_active")][:MAX_SCENARIOS]

    if not deployable:
        record("Scenarios available", False, "empty catalog")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        record("Playwright installed", False, "pip install playwright && playwright install chromium")
        return 1

    checked = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(45000)
        page.add_init_script(f"""() => {{
          localStorage.setItem('access_token', '{token}');
        }}""")

        for sc in deployable:
            if checked >= MAX_SCENARIOS:
                break
            sid = sc.get("id")
            slug = sc.get("slug", "")
            if not sid:
                continue
            st, data = api_post(f"/labs/{sid}/start/", token=token)
            if st not in (200, 201, 202):
                record(f"Lab start {slug}", False, str(data.get("error", st))[:80])
                continue
            session_id = data.get("session_id") or data.get("id")
            if not session_id:
                continue
            if not _wait_running(token, session_id):
                record(f"Lab running {slug}", False, "timeout or failed")
                try:
                    api_post(f"/labs/{session_id}/stop/", token=token)
                except Exception:
                    pass
                continue
            _check_lab_page(page, session_id, slug)
            checked += 1
            try:
                api_post(f"/labs/{session_id}/stop/", token=token)
            except Exception:
                pass

        browser.close()

    if checked == 0:
        record("Lab UI scenarios checked", False, "none completed")
    else:
        record("Lab UI scenarios checked", True, str(checked))

    print(f"\nRESULT: {passed} passed, {failed} failed")
    for e in errors[:15]:
        print(f"  - {e}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
