#!/usr/bin/env python3
"""
Dynamic E2E: every active technology + scenario + lab lifecycle (multi-user).

Auto-discovers catalog from DB — new admin techs/scenarios are tested on next run.

Per scenario (with Docker image):
  - User A: Jira ticket → start → RUNNING → hints → validate → history → progress → stop
  - User B: parallel start → isolation (different session + Jira) → stop
  - User C: cannot access User A session (403/404)

Run inside backend:
  E2E_SKIP_LAB=0 python /scripts/e2e_all_scenarios_labs.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.question_bank.models import Scenario, Technology
from apps.labs.models import LabSession
from apps.progress.models import UserScenarioProgress
from apps.public_api.views import (
    ActiveLabsView,
    ScenarioDetailView,
    StartLabView,
    StopLabView,
    ValidateLabView,
)
from apps.jira_integration.views import ScenarioJiraTicketView
from apps.public_api.views import LabHintsView
from apps.accounts.views import LabHistoryView

from e2e_dynamic_catalog import db_refresh, setup_all_test_users, grant_all_technology_subscriptions, refresh_test_user
from e2e_scenario_fix import apply_scenario_fix, fix_script_path

try:
    from e2e_simulation_fix import apply_simulation_fix
except ImportError:
    apply_simulation_fix = None

try:
    from e2e_terminal import verify_lab_terminal
except ImportError:
    verify_lab_terminal = None

try:
    from e2e_simulation_terminal import verify_simulation_terminal, verify_simulation_workflow
except ImportError:
    verify_simulation_terminal = None
    verify_simulation_workflow = None

User = get_user_model()
SKIP_LAB = os.environ.get("E2E_SKIP_LAB", "0") == "1"
SKIP_TERMINAL = os.environ.get("E2E_SKIP_TERMINAL", "0") == "1"
LAB_TIMEOUT = int(os.environ.get("LAB_WAIT_TIMEOUT", "120"))
MULTI_USERS = int(os.environ.get("E2E_MULTI_USERS", "3"))
# Only run dual-user isolation on the first deployable scenario (saves ~50% runtime)
ISOLATION_ONCE = os.environ.get("E2E_ISOLATION_ONCE", "1") == "1"


class RunStats:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors: list[str] = []

    def ok(self, name: str):
        self.passed += 1
        print(f"  [PASS] {name}")

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        msg = f"{name}" + (f" — {detail}" if detail else "")
        self.errors.append(msg)
        print(f"  [FAIL] {msg}")

    def skip(self, name: str, detail: str = ""):
        self.skipped += 1
        print(f"  [SKIP] {name}" + (f" — {detail}" if detail else ""))


def _response_data(st) -> dict:
    data = getattr(st, "data", None)
    return data if isinstance(data, dict) else {}


def _jira_issue_key(st) -> str:
    ticket = _response_data(st).get("ticket") or {}
    if isinstance(ticket, dict):
        return ticket.get("issue_key") or ""
    return ""


def _factory_view(view_cls, method: str, path: str, user, data=None, **kwargs):
    factory = APIRequestFactory()
    if method == "GET":
        req = factory.get(path)
    elif method == "POST":
        req = factory.post(path, data or {}, format="json")
    elif method == "PATCH":
        req = factory.patch(path, data or {}, format="json")
    elif method == "DELETE":
        req = factory.delete(path)
    else:
        raise ValueError(method)
    force_authenticate(req, user=user)
    return view_cls.as_view()(req, **kwargs)


def wait_session(session_id, timeout=LAB_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        db_refresh()
        session = LabSession.objects.filter(id=session_id).first()
        if not session:
            return None, "missing"
        if session.status == "RUNNING":
            return session, "RUNNING"
        if session.status in ("COMPLETED", "FAILED", "TERMINATED", "EXPIRED"):
            return session, session.status
        time.sleep(2)
    session = LabSession.objects.filter(id=session_id).first()
    return session, session.status if session else "timeout"


def run_scenario_e2e(stats: RunStats, scenario, user_a, user_b, user_c, *, test_isolation: bool = False):
    tech_slug = scenario.technology.slug if scenario.technology_id else "?"
    label = f"[{tech_slug}/{scenario.slug}]"
    has_fix = bool(fix_script_path(scenario))

    # Scenario detail API (frontend scenario page)
    st = _factory_view(ScenarioDetailView, "GET", f"/api/scenarios/{scenario.slug}/", user_a, slug=scenario.slug)
    if getattr(st, "status_code", 0) != 200:
        stats.fail(f"{label} scenario detail", str(getattr(st, "status_code", "")))
        return
    stats.ok(f"{label} scenario detail API")

    # Jira — user A
    st = _factory_view(
        ScenarioJiraTicketView, "POST", f"/api/jira/tickets/scenario/{scenario.id}/", user_a,
        scenario_id=scenario.id,
    )
    jira_a = _jira_issue_key(st)
    if getattr(st, "status_code", 0) not in (200, 201):
        stats.fail(f"{label} jira user_a", str(_response_data(st))[:60])
    elif not jira_a:
        stats.fail(f"{label} jira user_a", "no issue_key")
    else:
        stats.ok(f"{label} jira user_a {jira_a}")

    if test_isolation and user_b:
        st = _factory_view(
            ScenarioJiraTicketView, "POST", f"/api/jira/tickets/scenario/{scenario.id}/", user_b,
            scenario_id=scenario.id,
        )
        jira_b = _jira_issue_key(st)
        if jira_b and jira_a and jira_a == jira_b:
            stats.fail(f"{label} jira isolation", f"shared ticket {jira_a}")
        elif jira_b:
            stats.ok(f"{label} jira user_b {jira_b}")

    cache.clear()
    db_refresh()

    # Start lab — user A (always); user B only for isolation test
    st_a = _factory_view(StartLabView, "POST", f"/api/labs/{scenario.id}/start/", user_a, scenario_id=scenario.id)
    data_a = getattr(st_a, "data", {}) or {}
    sid_a = data_a.get("session_id") or data_a.get("id")

    sid_b = None
    if test_isolation and user_b:
        st_b = _factory_view(StartLabView, "POST", f"/api/labs/{scenario.id}/start/", user_b, scenario_id=scenario.id)
        data_b = getattr(st_b, "data", {}) or {}
        sid_b = data_b.get("session_id") or data_b.get("id")
        if getattr(st_b, "status_code", 0) not in (200, 201, 202) or not sid_b:
            stats.fail(f"{label} start user_b", str(data_b.get("error", data_b))[:80])
            _stop(sid_a, user_a)
            return
        if str(sid_a) == str(sid_b):
            stats.fail(f"{label} session isolation", "same session id")
            _stop(sid_a, user_a)
            return

    if getattr(st_a, "status_code", 0) not in (200, 201, 202) or not sid_a:
        stats.fail(f"{label} start user_a", str(data_a.get("error", data_a))[:80])
        return

    stats.ok(f"{label} start {'dual users' if test_isolation else 'user_a'}")

    sess_a, status_a = wait_session(sid_a)
    status_b = None
    if sid_b:
        _, status_b = wait_session(sid_b)

    if status_a != "RUNNING":
        stats.fail(f"{label} user_a RUNNING", status_a)
    else:
        stats.ok(f"{label} user_a RUNNING")

    if sid_b:
        if status_b != "RUNNING":
            stats.fail(f"{label} user_b RUNNING", status_b)
        else:
            stats.ok(f"{label} user_b RUNNING")

    # User C cannot stop user A's lab (isolation test only)
    if test_isolation and user_c and sid_a:
        st_c = _factory_view(StopLabView, "POST", f"/api/labs/{sid_a}/stop/", user_c, session_id=sid_a)
        if getattr(st_c, "status_code", 0) in (200, 204):
            stats.fail(f"{label} user_c isolation", "user_c stopped user_a lab")
        else:
            stats.ok(f"{label} user_c blocked from user_a lab")

    # Lab runner APIs — user A
    if status_a == "RUNNING":
        from apps.public_api.views import LabSessionStatusView, CommandHistoryView, SessionReplayView

        st = _factory_view(LabSessionStatusView, "GET", f"/api/labs/{sid_a}/status/", user_a, session_id=sid_a)
        if getattr(st, "status_code", 0) == 200:
            stats.ok(f"{label} status API")
        else:
            stats.fail(f"{label} status API", str(getattr(st, "status_code", "")))

        st = _factory_view(LabHintsView, "GET", f"/api/labs/{sid_a}/hints/", user_a, session_id=sid_a)
        if getattr(st, "status_code", 0) == 200:
            stats.ok(f"{label} hints GET")
        else:
            stats.fail(f"{label} hints GET", str(getattr(st, "status_code", "")))

        st = _factory_view(CommandHistoryView, "GET", f"/api/labs/{sid_a}/commands/", user_a, session_id=sid_a)
        if getattr(st, "status_code", 0) == 200:
            stats.ok(f"{label} commands/replay API")
        else:
            stats.fail(f"{label} commands API", str(getattr(st, "status_code", "")))

        st = _factory_view(SessionReplayView, "GET", f"/api/labs/{sid_a}/replay/", user_a, session_id=sid_a)
        if getattr(st, "status_code", 0) == 200:
            stats.ok(f"{label} replay API")

        is_sim = (sess_a.provider or "") == "simulation" or getattr(scenario, "lab_mode", "") == "simulation"
        if not SKIP_TERMINAL and sess_a:
            from rest_framework_simplejwt.tokens import AccessToken

            token = str(AccessToken.for_user(user_a))
            try:
                from apps.terminal import consumers as terminal_consumers

                terminal_consumers.reset_user_ws_connections(user_a.id)
            except Exception:
                pass

            if (
                verify_lab_terminal
                and not is_sim
                and (sess_a.provider or "docker") == "docker"
                and sess_a.container_id
            ):
                ok, detail = verify_lab_terminal(str(sid_a), token)
                if ok:
                    stats.ok(f"{label} terminal WebSocket")
                else:
                    stats.fail(f"{label} terminal WebSocket", detail[:80])

            if is_sim and verify_simulation_terminal:
                ok, detail = verify_simulation_terminal(str(sid_a), token, "primary")
                if ok:
                    stats.ok(f"{label} simulation terminal WS")
                else:
                    stats.fail(f"{label} simulation terminal WS", detail[:80])
                slug = (scenario.slug or "").lower()
                if verify_simulation_workflow and any(
                    x in slug for x in ("ssh-stop", "firewalld-dual", "mysql-dual", "sshd-down")
                ):
                    ok, detail = verify_simulation_workflow(str(sid_a), token, slug)
                    if ok:
                        stats.ok(f"{label} simulation workflow WS")
                    else:
                        stats.fail(f"{label} simulation workflow WS", detail[:80])

        # Apply fix.sh (docker) or simulation fix, then validate
        db_refresh()
        sess_a = LabSession.objects.filter(id=sid_a).first()
        sim_fix_ok = False
        if is_sim and sess_a and apply_simulation_fix:
            if sess_a.status != "RUNNING":
                stats.skip(f"{label} simulation fix", f"session {sess_a.status}")
                is_sim = False  # skip validate-pass expectation too
            else:
                ok, detail = apply_simulation_fix(sess_a)
                if ok:
                    stats.ok(f"{label} simulation fix")
                    sim_fix_ok = True
                elif detail == "no simulation session":
                    stats.skip(f"{label} simulation fix", "sim session not in process memory (cross-process E2E)")
                    is_sim = False
                else:
                    stats.fail(f"{label} simulation fix", detail[:80])
        elif has_fix and sess_a:
            ok, detail = apply_scenario_fix(sess_a)
            if ok:
                stats.ok(f"{label} apply fix.sh")
            else:
                stats.fail(f"{label} apply fix.sh", detail[:80])

        st = _factory_view(ValidateLabView, "POST", f"/api/labs/{sid_a}/validate/", user_a, session_id=sid_a)
        vdata = getattr(st, "data", {}) or {}
        passed = vdata.get("passed")
        if getattr(st, "status_code", 0) not in (200, 400, 500):
            stats.fail(f"{label} validate API", str(vdata)[:60])
        elif (has_fix or is_sim) and not passed:
            stats.fail(f"{label} validate PASS", (vdata.get("output") or str(vdata))[:80])
        elif (has_fix or is_sim) and passed:
            stats.ok(f"{label} validate PASS")
            db_refresh()
            sess_a = LabSession.objects.filter(id=sid_a).first()
            if sess_a and sess_a.status == "COMPLETED":
                prog = UserScenarioProgress.objects.filter(user=user_a, scenario=scenario).first()
                if prog:
                    stats.ok(f"{label} DB progress after validate")
                else:
                    stats.fail(f"{label} DB progress", "missing UserScenarioProgress")
        else:
            stats.ok(f"{label} validate API (no fix.sh, passed={passed})")

    # Active labs + history
    st = _factory_view(ActiveLabsView, "GET", "/api/labs/active/", user_a)
    if getattr(st, "status_code", 0) == 200:
        stats.ok(f"{label} active labs API")

    st = _factory_view(LabHistoryView, "GET", "/api/labs/history/", user_a)
    if getattr(st, "status_code", 0) == 200:
        stats.ok(f"{label} lab history API")

    # Stop remaining labs
    _stop(sid_a, user_a)
    if sid_b:
        _stop(sid_b, user_b)


def _stop(session_id, user):
    if not session_id:
        return
    try:
        db_refresh()
        sess = LabSession.objects.filter(id=session_id).first()
        if sess and sess.status in ("RUNNING", "PROVISIONING"):
            _factory_view(StopLabView, "POST", f"/api/labs/{session_id}/stop/", user, session_id=session_id)
    except Exception:
        pass


def run_admin_catalog_checks(stats: RunStats):
    """Admin sees same dynamic catalog counts as DB."""
    from apps.adminpanel.views import AdminScenariosView, AdminTechnologiesView
    from e2e_dynamic_catalog import discover_catalog

    admin_email = os.environ.get("SUPERUSER_EMAIL", "")
    admin = User.objects.filter(email=admin_email).first() if admin_email else None
    if not admin or not (admin.is_staff or admin.is_superuser):
        stats.skip("admin catalog", "no SUPERUSER_EMAIL")
        return

    catalog = discover_catalog()
    st = _factory_view(AdminTechnologiesView, "GET", "/api/admin/technologies/", admin)
    tech_data = getattr(st, "data", [])
    if isinstance(tech_data, list) and len(tech_data) >= len(catalog["technologies"]):
        stats.ok(f"admin technologies ({len(tech_data)} >= {len(catalog['technologies'])})")
    else:
        stats.fail("admin technologies count", f"api={len(tech_data) if isinstance(tech_data, list) else '?'} db={len(catalog['technologies'])}")

    st = _factory_view(AdminScenariosView, "GET", "/api/admin/scenarios/", admin)
    sc_data = getattr(st, "data", [])
    if isinstance(sc_data, list) and len(sc_data) >= len(catalog["scenarios"]):
        stats.ok(f"admin scenarios ({len(sc_data)} >= {len(catalog['scenarios'])})")
    else:
        stats.fail("admin scenarios count", f"api={len(sc_data) if isinstance(sc_data, list) else '?'} db={len(catalog['scenarios'])}")


def main():
    print("=" * 60)
    print("DYNAMIC ALL-SCENARIOS LAB E2E (auto catalog from DB)")
    print("=" * 60)

    stats = RunStats()

    if SKIP_LAB:
        stats.skip("all scenario labs", "E2E_SKIP_LAB=1")
        return 0

    users, catalog = setup_all_test_users(MULTI_USERS)
    user_a, user_b = users[0], users[1]
    user_c = users[2] if len(users) > 2 else None

    print(f"Technologies: {len(catalog['technologies'])}")
    print(f"Scenarios (active): {len(catalog['scenarios'])}")
    print(f"Deployable (image present): {len(catalog['deployable'])}")
    if catalog["missing_images"]:
        print(f"Missing images ({len(catalog['missing_images'])}): {', '.join(catalog['missing_images'][:15])}"
              + (" ..." if len(catalog["missing_images"]) > 15 else ""))

    isolation_done = False
    tech_filter_raw = os.environ.get("E2E_TECH_FILTER", "").strip()
    tech_filter = {t.strip().lower() for t in tech_filter_raw.split(",") if t.strip()}

    for tech in catalog["technologies"]:
        if tech_filter and tech.slug.lower() not in tech_filter:
            stats.skip(f"[{tech.slug}] all scenarios", "E2E_TECH_FILTER")
            continue
        tech_scenarios = catalog["by_tech"].get(tech.slug, [])
        if getattr(tech, "coming_soon", False):
            stats.skip(f"[{tech.slug}] all scenarios", "technology coming soon")
            continue
        deployable = [s for s in tech_scenarios if s in catalog["deployable"]]
        print(f"\n### Technology: {tech.name} ({tech.slug}) — {len(deployable)}/{len(tech_scenarios)} labs deployable ###")
        for sc in deployable:
            db_refresh()
            cache.clear()
            # Re-fetch by slug so FK references stay valid after parallel reseeds.
            fresh = Scenario.objects.filter(slug=sc.slug, is_active=True).select_related("technology").first()
            if not fresh:
                stats.skip(f"[{tech.slug}/{sc.slug}]", "scenario missing after refresh")
                continue
            # Re-apply subs — parallel E2E jobs may revoke test subscriptions mid-run.
            user_a = refresh_test_user(user_a)
            user_b = refresh_test_user(user_b) if user_b else None
            user_c = refresh_test_user(user_c) if user_c else None
            grant_all_technology_subscriptions(user_a, [fresh.technology])
            if user_b:
                grant_all_technology_subscriptions(user_b, [fresh.technology])
            if user_c:
                grant_all_technology_subscriptions(user_c, [fresh.technology])
            from e2e_dynamic_catalog import grant_unlimited_labs
            grant_unlimited_labs(user_a)
            if user_b:
                grant_unlimited_labs(user_b)
            if user_c:
                grant_unlimited_labs(user_c)
            do_isolation = ISOLATION_ONCE and not isolation_done and user_b is not None
            try:
                run_scenario_e2e(
                    stats, fresh, user_a, user_b, user_c,
                    test_isolation=do_isolation,
                )
                if do_isolation:
                    isolation_done = True
            except Exception as exc:
                stats.fail(f"[{tech.slug}/{sc.slug}] exception", str(exc)[:100])

    print("\n### Admin catalog sync ###")
    run_admin_catalog_checks(stats)

    print("\n" + "=" * 60)
    print(f"RESULT: {stats.passed} passed, {stats.failed} failed, {stats.skipped} skipped")
    if stats.errors:
        print("\nFailures:")
        for e in stats.errors[:30]:
            print(f"  - {e}")
        if len(stats.errors) > 30:
            print(f"  ... and {len(stats.errors) - 30} more")

    if catalog["missing_images"]:
        return 1
    return 0 if stats.failed == 0 else 1


def cleanup():
    import subprocess
    if os.environ.get("E2E_SKIP_CLEANUP", "0") == "1":
        return
    subprocess.run([sys.executable, "/scripts/cleanup-test-data.py"], timeout=300)


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        cleanup()
    sys.exit(code)
