#!/usr/bin/env python3
"""E2E tests for AI Interview Studio (free browser voice + admin control)."""

from __future__ import annotations

import os
import sys
import uuid

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from e2e_production_test import Suite, api, err_msg, login  # noqa: E402

ADMIN_EMAIL = os.environ.get("SUPERUSER_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("SUPERUSER_PASSWORD", "")


def run_interview_e2e(s: Suite) -> None:
    print("\n=== Interview Studio E2E ===")

    st, data = api("GET", "/api/interviews/plans/")
    s.record("GET interview plans", st == 200, st, err_msg(data))

    st, data = api("GET", "/api/interviews/voice/config/")
    ok = st == 200 and data.get("uses_paid_apis") is False and data.get("tts_provider") == "browser"
    s.record("Voice config is free browser", ok, st, str(data.get("tts_provider", "")))

    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        s.record("Interview admin tests", False, detail="SUPERUSER_EMAIL/PASSWORD not set")
        return

    admin_token, _ = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        s.record("Interview admin login", False)
        return

    admin_paths = [
        "/api/admin/interviews/overview/",
        "/api/admin/interviews/settings/",
        "/api/admin/interviews/tiers/",
        "/api/admin/interviews/voices/",
        "/api/admin/interviews/live/",
        "/api/admin/interviews/campaigns/",
        "/api/admin/interviews/questions/",
        "/api/admin/interviews/entitlements/",
        "/api/admin/interviews/join-requests/",
    ]
    for path in admin_paths:
        st, resp = api("GET", path, token=admin_token)
        s.record(f"Admin GET {path}", st == 200, st, err_msg(resp))

    st, settings = api("PUT", "/api/admin/interviews/settings/", token=admin_token, data={
        "enabled": True,
        "staff_free_by_default": True,
        "allow_admin_observer": True,
    })
    s.record("Admin PUT interview settings", st == 200, st, err_msg(settings))

    user_email = f"e2e-interview-{uuid.uuid4().hex[:8]}@fixitlab-test.local"
    user_password = "E2eInterviewPass123!"
    user_token = None

    st, otp_data = api("POST", "/api/auth/send-otp/", data={"email": user_email})
    if st == 200:
        try:
            sys.path.insert(0, "/app")
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            import django
            django.setup()
            from apps.accounts.models import EmailVerificationOTP
            otp_obj = EmailVerificationOTP.objects.filter(email=user_email).order_by("-created_at").first()
            if otp_obj:
                st, _ = api("POST", "/api/auth/verify-otp/", data={
                    "session_token": otp_obj.session_token,
                    "code": otp_obj.code,
                })
                st, reg = api("POST", "/api/auth/register/", data={
                    "email": user_email,
                    "password": user_password,
                    "session_token": otp_obj.session_token,
                })
                user_token = reg.get("access") if st in (200, 201) else None
        except Exception as exc:
            s.record("Interview user OTP setup", False, detail=str(exc)[:80])

    if not user_token:
        s.record("Interview user auth", False, detail="could not register test user")
        return
    s.record("Interview user auth", True)

    st, ent = api("GET", "/api/interviews/entitlement/", token=user_token)
    s.record("GET user entitlement", st == 200, st)

    st, grant = api("POST", "/api/admin/interviews/entitlements/", token=admin_token, data={
        "email": user_email,
        "grant_free": True,
    })
    s.record("Admin grant free interview", st == 200, st, err_msg(grant))

    st, ent2 = api("GET", "/api/interviews/entitlement/", token=user_token)
    free_ok = st == 200 and (ent2.get("is_admin_granted_free") or ent2.get("is_complimentary"))
    s.record("User has admin-granted free", free_ok, st)

    st, camp = api("POST", "/api/interviews/campaigns/", token=user_token, data={"round_count": 3})
    s.record("POST create campaign", st in (200, 201), st, err_msg(camp))

    if st in (200, 201) and camp.get("id"):
        campaign_id = camp["id"]
        st, detail = api("GET", f"/api/interviews/campaigns/{campaign_id}/", token=user_token)
        s.record("GET campaign detail", st == 200, st)
        rounds = detail.get("rounds") or camp.get("rounds") or []
        if rounds:
            round_id = rounds[0]["id"]
            st, _ = api("GET", f"/api/interviews/rounds/{round_id}/join-requests/", token=user_token)
            s.record("GET join-requests (candidate)", st == 200, st)


def main() -> int:
    s = Suite()
    run_interview_e2e(s)
    failed = s.failed
    print(f"\n=== Interview E2E: {len(s.results) - len(failed)}/{len(s.results)} passed ===")
    for r in failed:
        print(f"  FAIL {r.name}: {r.detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
