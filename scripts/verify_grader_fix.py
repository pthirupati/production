#!/usr/bin/env python
"""Grader fix-contract harness (standalone diagnostic + gate).

For every simulation scenario, verify the FAIL-CLOSED contract the E2E relies on:

    unfixed state  -> validate FAIL   (Check-Solution must not auto-pass)
    E2E fix applied -> validate PASS   (the documented remediation clears it)

Classification per scenario:
    GOOD        pre=FAIL, post=PASS   (correct, E2E-safe)
    FAIL_OPEN   pre=PASS              (grader auto-passes on the broken state)
    BROKEN_FIX  pre=FAIL, post=FAIL   (E2E fix does not clear the check —
                would turn the currently-green prod E2E RED)
    NO_FIX      pre=FAIL, fix returns "no simulation fix map / no session"
                (E2E SKIPS the validate-PASS assertion for these — fail-closed
                AND E2E-safe, but not driven to a pass by any automated fix)

Faithful to the runtime path (apps.labs.provisioner.simulation_provisioner
.SimulationProvisioner.run_validation):

    script = resolve_simulation_validation_script(slug, db_script)
    engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
    passed, output = validate_simulation_state(engine.state, script, engine=engine)

The E2E fix (scripts/e2e_simulation_fix.apply_simulation_fix) operates on a
LabSession + the registered in-process sim session. We reproduce that by
registering a synthetic sim session for the freshly-built engine and wrapping it
in a lightweight fake LabSession, then calling apply_simulation_fix against the
SAME engine/state we validated pre-fix. This exercises the real fix wiring.

Run:
    backend/.venv/bin/python scripts/verify_grader_fix.py [slug ...]
    backend/.venv/bin/python scripts/verify_grader_fix.py --tech linux
    backend/.venv/bin/python scripts/verify_grader_fix.py --only-fail-open

This script performs NO DB writes and no commits.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

# ── Django bootstrap (mirrors scripts/scan_grader_integrity.py) ──
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
import os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

import django  # noqa: E402

django.setup()

from apps.labs.provisioner.simulation.shell import (  # noqa: E402
    _SIM_SESSIONS,
    register_sim_session,
    drop_sim_session,
)
from apps.labs.provisioner.simulation.sim_types import normalize_sim_type  # noqa: E402
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine  # noqa: E402
from apps.labs.provisioner.simulation.validation import (  # noqa: E402
    resolve_simulation_validation_script,
    validate_simulation_state,
)

import e2e_simulation_fix  # noqa: E402
from e2e_simulation_fix import apply_simulation_fix  # noqa: E402

_NO_MATCH_OUTPUTS = {
    "No validation checks matched this simulation script",
    "NO_VALIDATION_SCRIPT",
    "Validation not configured — fix the scenario before checking",
}


# ── Faithful runtime dispatch (mirrors SimulationProvisioner.run_validation) ──
# Several technologies do NOT validate through validate_simulation_state at
# runtime — run_validation routes them to a dedicated self-contained engine
# validator keyed by session_id + slug (windows, vmware, terraform/aws, nmap,
# wireshark, ai-agent, peoplesoft, data-dashboard, awx, and baremetal-IPMI).
# Those validators build their own fail-closed world from the preset, so a
# scanner that only exercises validate_simulation_state MIS-classifies them as
# fail-open. We reproduce the exact slug/sim_type gating so the harness reflects
# what Check-Solution actually runs.
def _dedicated_validator(slug: str, raw_sim_type: str):
    """Return a zero-arg callable -> (passed, output) if this scenario routes to
    a dedicated engine validator at runtime, else None."""
    low = (slug or "").lower()
    st = (raw_sim_type or "").lower()
    import uuid as _uuid

    def _mk(ensure, validate):
        def _run():
            sid = f"verify-eng-{_uuid.uuid4().hex}"
            ensure(sid, slug)
            return validate(sid, slug)
        return _run

    if "vmware" in low:
        # Cross-technology linux/k8s labs whose slug contains "vmware" are NOT
        # routed to the vCenter validator (see SimulationProvisioner.run_validation)
        # — they validate through validate_simulation_state. Mirror that here.
        try:
            from apps.labs.provisioner.simulation.vmware_bridge import (
                is_cross_tech_scenario as _is_xtech,
            )
        except Exception:
            _is_xtech = lambda _s: False  # noqa: E731
        if not _is_xtech(low):
            from apps.vmware_sim.engine import validate_vmware_lab, _ensure_session
            return _mk(_ensure_session, validate_vmware_lab)
    if low.startswith("nmap-") or st == "nmap":
        from apps.vmware_sim.nmap_engine import validate_nmap_lab, _ensure_session
        return _mk(_ensure_session, validate_nmap_lab)
    if low.startswith("wireshark-") or st == "wireshark":
        from apps.vmware_sim.wireshark_engine import validate_wireshark_lab, _ensure_session
        return _mk(_ensure_session, validate_wireshark_lab)
    if low.startswith("agent-") or st == "ai-agent":
        from apps.vmware_sim.aiml_engine import validate_aiml_lab, _ensure_session
        return _mk(_ensure_session, validate_aiml_lab)
    if low.startswith(("win-gui-", "windows-", "academy-windows-")) or st in ("windows", "windows-server"):
        from apps.vmware_sim.windows_engine import validate_windows_lab, _ensure_session
        return _mk(_ensure_session, validate_windows_lab)
    if low.startswith("ps-") or st == "peoplesoft":
        from apps.vmware_sim.peoplesoft_engine import validate_peoplesoft_lab, _ensure_session
        return _mk(_ensure_session, validate_peoplesoft_lab)
    if low.startswith("ds-dashboard-") or st == "data-dashboard":
        from apps.vmware_sim.datascience_engine import validate_datascience_lab, _ensure_session
        return _mk(_ensure_session, validate_datascience_lab)
    if "awx" in low or "tower" in low or st == "ansible-awx":
        from apps.vmware_sim.awx_engine import validate_awx_lab, _ensure as awx_ensure
        return _mk(awx_ensure, validate_awx_lab)
    if st == "terraform" or low.startswith("terraform-"):
        from apps.vmware_sim.terraform_engine import validate_terraform_lab, _ensure as tf_ensure
        return _mk(tf_ensure, validate_terraform_lab)
    if st == "baremetal" and any(k in low for k in ("maas", "lxd", "lxc", "kvm", "virsh", "ipmi")):
        from apps.vmware_sim.baremetal_engine import validate_baremetal_lab, _ensure as bm_ensure
        return _mk(bm_ensure, validate_baremetal_lab)
    return None


# ── Fake LabSession / Scenario / Technology so apply_simulation_fix runs ──
class _FakeTech:
    def __init__(self, slug: str):
        self.slug = slug


class _FakeScenario:
    def __init__(self, slug: str, tech: str, sim_type: str, validation_script: str = ""):
        self.slug = slug
        self.technology = _FakeTech(tech)
        self.technology_id = 1
        self.simulation_type = sim_type
        # Runtime carries the on-disk check.sh here (seed_scenarios loads it);
        # provide it so any fixer re-validation mirrors production.
        self.validation_script = validation_script


class _FakeSession:
    def __init__(self, sid: str, slug: str, tech: str, sim_type: str, validation_script: str = ""):
        self.id = sid
        self.scenario = _FakeScenario(slug, tech, sim_type, validation_script)
        self.container_id = ""
        self.instance_id = ""
        self.provider = "simulation"


def scenarios_root() -> Path:
    for candidate in (Path("/scenarios"), _REPO_ROOT / "scenarios"):
        if candidate.is_dir():
            return candidate
    return _REPO_ROOT / "scenarios"


def _iter_from_db():
    try:
        from apps.question_bank.models import Scenario

        qs = (
            Scenario.objects.filter(is_active=True)
            .select_related("technology")
            .only("slug", "validation_script", "simulation_type", "technology__slug")
        )
        rows = []
        for sc in qs.iterator():
            tech = sc.technology.slug if sc.technology_id else "unknown"
            rows.append(
                (sc.slug or "", tech, getattr(sc, "simulation_type", "") or "generic",
                 sc.validation_script or "")
            )
        return rows or None
    except Exception:
        return None


def _iter_from_fs():
    import yaml

    root = scenarios_root()
    rows = []
    if not root.is_dir():
        return rows
    seen: set[str] = set()
    for tech_dir in sorted(root.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name == "shared":
            continue
        tech = tech_dir.name
        for sd in sorted(tech_dir.iterdir()):
            if not sd.is_dir():
                continue
            y = sd / "scenario.yaml"
            if not y.is_file():
                continue
            try:
                data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            slug = data.get("slug") or sd.name
            # De-dup: same slug can appear under multiple tech dirs; the runtime
            # keys scenarios by slug, so classify each slug once.
            if slug in seen:
                continue
            seen.add(slug)
            sim_type = data.get("simulation_type") or "generic"
            check = sd / "check.sh"
            script = check.read_text(encoding="utf-8") if check.is_file() else ""
            rows.append((slug, data.get("technology") or tech, sim_type, script))
    return rows


def _isolate(sid: str) -> None:
    """Clear shared caches so one scenario cannot contaminate the next.

    Cross-technology scenarios read/write the VMware bridge and Django cache
    keyed by session_id. Running the whole catalog in a single process would
    otherwise let a prior scenario's fix leak state (e.g. a hot-added disk) into
    the next scenario's pre-fix validation, producing false FAIL_OPEN/BROKEN_FIX.
    """
    try:
        from apps.labs.provisioner.simulation.vmware_bridge import clear as _bridge_clear
        _bridge_clear(sid)
        _bridge_clear("")
    except Exception:
        pass
    try:
        from django.core.cache import cache
        cache.clear()
    except Exception:
        pass


def _build_engine(slug: str, sim_type: str, sid: str) -> UnifiedSimulationEngine:
    norm_type = normalize_sim_type(sim_type)
    engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=norm_type)
    # Stamp a unique session id on the state BEFORE validation so any bridge
    # lookup uses this scenario's (freshly cleared) key, not a leaked one.
    try:
        engine.shell.state.session_id = sid
    except Exception:
        pass
    return engine


def _validate(slug: str, sim_type: str, db_script: str, engine=None):
    """Validate the (unfixed) engine, return (engine, script, passed, output)."""
    if engine is None:
        engine = _build_engine(slug, sim_type, f"verify-{uuid.uuid4().hex}")
    script = resolve_simulation_validation_script(slug, db_script or "")
    passed, output = validate_simulation_state(engine.state, script, engine=engine)
    return engine, script, passed, output


def _apply_fix(engine: UnifiedSimulationEngine, slug: str, tech: str, sim_type: str, sid: str,
               db_script: str = ""):
    """Register the engine as a sim session, run the real E2E fix, return (ok, detail)."""
    register_sim_session(sid, sid, normalize_sim_type(sim_type), {"engine": engine})
    try:
        session = _FakeSession(sid, slug, tech, sim_type, db_script)
        try:
            ok, detail = apply_simulation_fix(session)
        except Exception as exc:  # a raising fix is treated as no-fix, reported
            return None, f"FIX-EXC {type(exc).__name__}: {exc}"
        return ok, detail
    finally:
        drop_sim_session(sid)
        # Clear caches the fix may have written (vmware/terraform/baremetal engine
        # sessions live in the Django cache) so nothing leaks into the next
        # scenario and the classification stays deterministic.
        _isolate(sid)


def classify(slug: str, tech: str, sim_type: str, db_script: str) -> dict:
    # ── Dedicated-validator technologies (windows/vmware/terraform/…) ──
    # Runtime routes these AWAY from validate_simulation_state to a self-contained
    # engine validator. Reproduce that so the harness reflects Check-Solution.
    ded = None
    try:
        ded = _dedicated_validator(slug, sim_type)
    except Exception:
        ded = None
    sid = f"verify-{uuid.uuid4().hex}"
    _isolate(sid)
    if ded is not None:
        try:
            dp, do = ded()
        except Exception as exc:
            return {"slug": slug, "tech": tech, "cls": "DEDICATED",
                    "detail": f"engine-validator EXC {type(exc).__name__}: {exc}"}
        if dp:
            # A dedicated engine that auto-passes on the fresh world IS fail-open.
            return {"slug": slug, "tech": tech, "cls": "FAIL_OPEN",
                    "detail": f"[dedicated] {do}"}
        return {"slug": slug, "tech": tech, "cls": "DEDICATED",
                "detail": f"pre=FAIL (dedicated engine): {do}"}

    try:
        engine = _build_engine(slug, sim_type, sid)
        engine, script, pre_pass, pre_out = _validate(slug, sim_type, db_script, engine=engine)
    except Exception as exc:
        return {"slug": slug, "tech": tech, "cls": "ERROR",
                "detail": f"validate(pre) {type(exc).__name__}: {exc}"}

    if pre_pass:
        return {"slug": slug, "tech": tech, "cls": "FAIL_OPEN",
                "detail": pre_out}

    # pre=FAIL — apply the E2E fix to the SAME engine, re-validate.
    fix_ok, fix_detail = _apply_fix(engine, slug, tech, sim_type, sid, db_script)

    # A fix that declines (no map / no session) => E2E SKIPS the pass assertion.
    if fix_ok is not True:
        no_fix = (
            isinstance(fix_detail, str)
            and ("no simulation fix map" in fix_detail
                 or fix_detail == "no simulation session")
        )
        cls = "NO_FIX" if no_fix else "BROKEN_FIX"
        return {"slug": slug, "tech": tech, "cls": cls,
                "detail": f"pre=FAIL fix_ok={fix_ok}: {fix_detail}"}

    try:
        post_pass, post_out = validate_simulation_state(engine.state, script, engine=engine)
    except Exception as exc:
        return {"slug": slug, "tech": tech, "cls": "BROKEN_FIX",
                "detail": f"validate(post) {type(exc).__name__}: {exc}"}

    if post_pass:
        return {"slug": slug, "tech": tech, "cls": "GOOD", "detail": ""}
    # E2E-SAFE post-FAIL: the runtime E2E only asserts validate==PASS when the
    # validator ACTUALLY matched checks. When it reports "No validation checks
    # matched" / "Validation not configured", the E2E SKIPS the pass assertion
    # (e2e_all_scenarios_labs.py L347-348). Such a scenario is fail-closed AND
    # E2E-safe — never an auto-pass and never a red. Classify as NO_MATCH, not
    # BROKEN_FIX, so the gate only flags conversions that would truly red the E2E.
    if post_out in _NO_MATCH_OUTPUTS or "No validation checks matched" in (post_out or ""):
        return {"slug": slug, "tech": tech, "cls": "NO_MATCH",
                "detail": f"fix ok='{fix_detail}', validate not covered: {post_out}"}
    return {"slug": slug, "tech": tech, "cls": "BROKEN_FIX",
            "detail": f"fix ok='{fix_detail}' but validate still FAIL: {post_out}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", help="specific slug(s) to check")
    ap.add_argument("--tech", default="", help="only this technology")
    ap.add_argument("--only-fail-open", action="store_true",
                    help="only re-check slugs currently classed FAIL_OPEN")
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    args = ap.parse_args()

    rows = _iter_from_db()
    source = "database"
    if not rows:
        rows = _iter_from_fs()
        source = "filesystem"

    if args.slugs:
        want = set(args.slugs)
        rows = [r for r in rows if r[0] in want]
    if args.tech:
        rows = [r for r in rows if r[1] == args.tech]

    results: list[dict] = []
    for slug, tech, sim_type, db_script in rows:
        results.append(classify(slug, tech, sim_type, db_script))

    if args.only_fail_open:
        results = [r for r in results if r["cls"] in ("FAIL_OPEN", "BROKEN_FIX")]

    counts: Counter[str] = Counter(r["cls"] for r in results)
    by_tech: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        by_tech[r["tech"]][r["cls"]] += 1

    fail_open = sorted(r["slug"] for r in results if r["cls"] == "FAIL_OPEN")
    broken_fix = [r for r in results if r["cls"] == "BROKEN_FIX"]
    errors = [r for r in results if r["cls"] == "ERROR"]

    payload = {
        "source": source,
        "total": len(results),
        "counts": dict(counts),
        "fail_open_slugs": fail_open,
        "broken_fix": [{"slug": r["slug"], "tech": r["tech"], "detail": r["detail"]}
                       for r in broken_fix],
        "errors": [{"slug": r["slug"], "detail": r["detail"]} for r in errors],
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print("=" * 72)
    print(f"GRADER FIX-CONTRACT HARNESS  (source: {source})")
    print("=" * 72)
    print(f"Scenarios checked : {len(results)}")
    for cls in ("GOOD", "DEDICATED", "NO_MATCH", "NO_FIX", "FAIL_OPEN", "BROKEN_FIX", "ERROR"):
        if counts.get(cls):
            print(f"  {cls:<12}: {counts[cls]}")
    print()

    print("Per-technology breakdown (tech: GOOD/DED/NO_MATCH/NO_FIX/FAIL_OPEN/BROKEN_FIX/ERR)")
    print("-" * 60)
    for tech in sorted(by_tech):
        c = by_tech[tech]
        line = (f"  {tech:<16}: {c['GOOD']}/{c['DEDICATED']}/{c['NO_MATCH']}/{c['NO_FIX']}/"
                f"{c['FAIL_OPEN']}/{c['BROKEN_FIX']}/{c['ERROR']}")
        if c["FAIL_OPEN"] or c["BROKEN_FIX"] or c["ERROR"]:
            line += "   <<<"
        print(line)
    print()

    if fail_open:
        print(f"FAIL_OPEN slugs ({len(fail_open)}):")
        for s in fail_open:
            print(f"  - {s}")
        print()
    if broken_fix:
        print(f"BROKEN_FIX slugs ({len(broken_fix)})  ***DANGER: would red the E2E***:")
        for r in broken_fix:
            print(f"  - {r['slug']} [{r['tech']}]: {r['detail'][:140]}")
        print()
    if errors:
        print(f"ERROR slugs ({len(errors)}):")
        for r in errors:
            print(f"  - {r['slug']}: {r['detail'][:140]}")
        print()

    print("JSON SUMMARY")
    print("-" * 40)
    print(json.dumps({k: payload[k] for k in ("source", "total", "counts")},
                     indent=2, sort_keys=True))
    # Non-zero exit if any BROKEN_FIX (the gate).
    return 1 if broken_fix else 0


if __name__ == "__main__":
    raise SystemExit(main())
