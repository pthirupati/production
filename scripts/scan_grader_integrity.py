#!/usr/bin/env python
"""Grader-integrity scanner (standalone, READ-ONLY diagnostic).

For every scenario, replicate the RUNTIME simulation validation on the UNFIXED
(broken) state and classify the outcome:

  FAIL-OPEN   — validate_simulation_state returned passed=True on the broken
                state (the grader auto-passes without any fix; a real problem).
  NO-MATCH    — validation ran but matched no substantive checks
                ("No validation checks matched this simulation script").
  FAIL-CLOSED — validation correctly returned passed=False for a real reason
                (the desired behaviour on the unfixed state).

Faithful to the runtime path used by the provisioner for terminal/simulation
labs (apps.labs.provisioner.simulation_provisioner.SimulationProvisioner
.run_validation, ~L597-599):

  script = resolve_simulation_validation_script(slug, db_script)
  engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
  passed, output = validate_simulation_state(engine.state, script, engine=engine)

The UnifiedSimulationEngine applies the scenario preset automatically when its
RHELShell is constructed with the scenario slug (scenario_presets
.apply_scenario_preset), so the engine.state IS the broken/unfixed state — the
same construction the provisioner uses.

Scenario source: the seeded DB when available (Scenario.validation_script holds
the check.sh text, as seed_scenarios.py loads it); otherwise walks
scenarios/<tech>/<slug>/scenario.yaml + check.sh from the filesystem.

Several technologies do NOT validate through validate_simulation_state at
runtime — SimulationProvisioner.run_validation routes them to a dedicated,
self-contained engine validator keyed by session_id + slug (windows, vmware,
terraform/aws, nmap, wireshark, ai-agent, peoplesoft, data-dashboard, awx, and
baremetal-IPMI). Those validators build their own fail-closed world from the
preset, so a scanner that only exercises validate_simulation_state MIS-classifies
them as fail-open. We reproduce the exact slug/sim_type gating (mirrored from
scripts/verify_grader_fix.py) so the report reflects what Check-Solution actually
runs — otherwise the ~40 windows/nmap labs show up as false-positive fail-opens.

Run:
    backend/.venv/bin/python scripts/scan_grader_integrity.py            # full report
    backend/.venv/bin/python scripts/scan_grader_integrity.py --check    # CI gate
    backend/.venv/bin/python scripts/scan_grader_integrity.py --check --allowlist FILE

--check      prints the FAIL-OPEN count + slugs and EXITS 1 if any fail-open
             grader exists (0 otherwise). Read-only; suitable for CI.
--allowlist  path to a newline-delimited file of known-tolerated slugs (a frozen
             list that can only shrink). Under --check the gate ignores fail-open
             slugs that appear in the allowlist and only fails on NEW ones.

This script performs NO writes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

# ── Django bootstrap (mirrors scripts/e2e_dynamic_catalog.py, but uses the
#    test settings + the repo's backend/ on sys.path so it runs off the checked
#    out tree with backend/.venv/bin/python). ──
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

import django  # noqa: E402

django.setup()

from apps.labs.provisioner.simulation.sim_types import normalize_sim_type  # noqa: E402
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine  # noqa: E402
from apps.labs.provisioner.simulation.validation import (  # noqa: E402
    resolve_simulation_validation_script,
    validate_simulation_state,
)

# Outputs validate_simulation_state emits for the "nothing matched" case.
_NO_MATCH_OUTPUTS = {
    "No validation checks matched this simulation script",
    "NO_VALIDATION_SCRIPT",
    "Validation not configured — fix the scenario before checking",
}


# ── Faithful runtime dispatch (mirrors SimulationProvisioner.run_validation and
#    scripts/verify_grader_fix.py._dedicated_validator). ──
# Technologies below are routed AWAY from validate_simulation_state to a
# dedicated engine validator at runtime. We reproduce the exact gating so the
# scanner classifies them by the validator Check-Solution actually invokes,
# rather than mis-flagging their (unused) check.sh as fail-open.
def _dedicated_validator(slug: str, raw_sim_type: str):
    """Return a zero-arg callable -> (passed, output) if this scenario routes to
    a dedicated engine validator at runtime, else None."""
    low = (slug or "").lower()
    st = (raw_sim_type or "").lower()

    def _mk(ensure, validate):
        def _run():
            sid = f"scan-eng-{uuid.uuid4().hex}"
            ensure(sid, slug)
            return validate(sid, slug)

        return _run

    if "vmware" in low:
        # Cross-technology linux/k8s labs whose slug contains "vmware" are NOT
        # routed to the vCenter validator — they validate through
        # validate_simulation_state. Mirror that here.
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
    if low.startswith(("win-gui-", "windows-", "academy-windows-")) or st in (
        "windows",
        "windows-server",
    ):
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
    if st == "baremetal" and any(
        k in low for k in ("maas", "lxd", "lxc", "kvm", "virsh", "ipmi")
    ):
        from apps.vmware_sim.baremetal_engine import validate_baremetal_lab, _ensure as bm_ensure
        return _mk(bm_ensure, validate_baremetal_lab)
    return None


def scenarios_root() -> Path:
    for candidate in (Path("/scenarios"), _REPO_ROOT / "scenarios"):
        if candidate.is_dir():
            return candidate
    return _REPO_ROOT / "scenarios"


def _iter_from_db():
    """Yield (slug, technology, sim_type, db_script) from the seeded DB, or None."""
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
                (
                    sc.slug or "",
                    tech,
                    getattr(sc, "simulation_type", "") or "generic",
                    sc.validation_script or "",
                )
            )
        return rows or None
    except Exception:
        return None


def _iter_from_fs():
    """Yield (slug, technology, sim_type, db_script) by walking the scenarios tree."""
    import yaml

    root = scenarios_root()
    rows = []
    if not root.is_dir():
        return rows
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
            sim_type = data.get("simulation_type") or "generic"
            check = sd / "check.sh"
            script = check.read_text(encoding="utf-8") if check.is_file() else ""
            rows.append((slug, data.get("technology") or tech, sim_type, script))
    return rows


def _first_check_line(script: str) -> str:
    """First substantive (non-comment, non-shebang) line of the check script."""
    for raw in (script or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line in ("true", ":", "exit 0"):
            continue
        return line[:120]
    return "(empty)"


def classify(slug: str, sim_type: str, db_script: str) -> tuple[str, str]:
    """Return (classification, output) replicating the runtime validation path.

    Scenarios that route to a dedicated engine validator at runtime are graded
    by that validator (not validate_simulation_state); we invoke it so their
    unused check.sh is not mis-flagged as fail-open.
    """
    # ── Dedicated-validator technologies (windows/vmware/terraform/…) ──
    try:
        ded = _dedicated_validator(slug, sim_type)
    except Exception:
        ded = None
    if ded is not None:
        try:
            dp, do = ded()
        except Exception as exc:
            return "ERROR", f"dedicated-engine {type(exc).__name__}: {exc}"
        # A dedicated engine that auto-passes on the fresh (unfixed) world IS a
        # real fail-open; otherwise it is fail-closed via its own validator.
        if dp:
            return "FAIL-OPEN", f"[dedicated] {do}"
        return "FAIL-CLOSED", f"[dedicated] {do}"

    norm_type = normalize_sim_type(sim_type)
    try:
        engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=norm_type)
        script = resolve_simulation_validation_script(slug, db_script or "")
        passed, output = validate_simulation_state(engine.state, script, engine=engine)
    except Exception as exc:  # engine/preset/validation error — record, don't crash
        return "ERROR", f"{type(exc).__name__}: {exc}"

    if passed:
        return "FAIL-OPEN", output
    if output in _NO_MATCH_OUTPUTS or "No validation checks matched" in (output or ""):
        return "NO-MATCH", output
    return "FAIL-CLOSED", output


def _load_allowlist(path: str | None) -> set[str]:
    """Read a newline-delimited allowlist of tolerated fail-open slugs.

    Blank lines and lines starting with '#' are ignored. A missing file is
    treated as an empty allowlist (so the gate fails on ANY fail-open).
    """
    if not path:
        return set()
    p = Path(path)
    if not p.is_file():
        return set()
    slugs: set[str] = set()
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        slugs.add(line)
    return slugs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Grader-integrity scanner (read-only). "
        "With --check, exits 1 if any fail-open grader exists."
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="strict CI gate: print fail-open count + slugs and exit 1 if any "
        "fail-open grader exists (outside the allowlist), else exit 0.",
    )
    ap.add_argument(
        "--allowlist",
        default=None,
        metavar="FILE",
        help="path to a newline-delimited file of known-tolerated fail-open "
        "slugs (a frozen list that can only shrink); the gate ignores these.",
    )
    args = ap.parse_args(argv)
    allowlist = _load_allowlist(args.allowlist)

    rows = _iter_from_db()
    source = "database"
    if not rows:
        rows = _iter_from_fs()
        source = "filesystem"

    classes: Counter[str] = Counter()
    fail_open: list[dict] = []
    fail_open_by_tech: Counter[str] = Counter()
    fail_open_by_first_line: dict[str, list[str]] = defaultdict(list)

    for slug, tech, sim_type, db_script in rows:
        cls, output = classify(slug, sim_type, db_script)
        classes[cls] += 1
        if cls == "FAIL-OPEN":
            first = _first_check_line(db_script)
            fail_open.append(
                {
                    "slug": slug,
                    "technology": tech,
                    "simulation_type": sim_type,
                    "first_check_line": first,
                    "grader_output": output,
                }
            )
            fail_open_by_tech[tech] += 1
            fail_open_by_first_line[first].append(slug)

    total = sum(classes.values())
    print("=" * 72)
    print(f"GRADER-INTEGRITY SCAN  (source: {source})")
    print("=" * 72)
    print(f"Scenarios scanned : {total}")
    for cls in ("FAIL-OPEN", "NO-MATCH", "FAIL-CLOSED", "ERROR"):
        if classes.get(cls):
            print(f"  {cls:<12}: {classes[cls]}")
    print()

    print("FAIL-OPEN by technology")
    print("-" * 40)
    for tech, cnt in fail_open_by_tech.most_common():
        print(f"  {tech:<18}: {cnt}")
    print()

    print("FAIL-OPEN grouped by first check line (count : line)")
    print("-" * 40)
    grouped = sorted(
        fail_open_by_first_line.items(), key=lambda kv: len(kv[1]), reverse=True
    )
    for line, slugs in grouped:
        print(f"  {len(slugs):>4} : {line}")
    print()

    all_fail_open_slugs = sorted(f["slug"] for f in fail_open)
    # Fail-open slugs NOT covered by the allowlist — these fail the gate.
    unlisted_fail_open = sorted(s for s in all_fail_open_slugs if s not in allowlist)
    # Allowlist entries that are no longer fail-open (allowlist should shrink).
    stale_allowlist = sorted(allowlist - set(all_fail_open_slugs))

    payload = {
        "source": source,
        "total_scanned": total,
        "counts": dict(classes),
        "fail_open_count": classes.get("FAIL-OPEN", 0),
        "fail_open_by_technology": dict(fail_open_by_tech.most_common()),
        "fail_open_by_first_check_line": {
            line: sorted(slugs) for line, slugs in grouped
        },
        "fail_open_slugs": all_fail_open_slugs,
        "allowlisted": sorted(allowlist),
        "unlisted_fail_open_slugs": unlisted_fail_open,
    }
    print("JSON SUMMARY")
    print("-" * 40)
    print(json.dumps(payload, indent=2, sort_keys=True))

    if not args.check:
        return 0

    # ── Strict CI gate ──────────────────────────────────────────────────────
    print()
    print("=" * 72)
    print("GRADER-INTEGRITY GATE (--check)")
    print("=" * 72)
    print(f"FAIL-OPEN graders          : {len(all_fail_open_slugs)}")
    print(f"Allowlisted (tolerated)    : {len(allowlist)}")
    print(f"Fail-open NOT allowlisted  : {len(unlisted_fail_open)}")
    if stale_allowlist:
        # Advisory only — the allowlist may only shrink, so flag entries that no
        # longer fail-open and can be removed. Does not fail the gate.
        print(
            "NOTE: allowlist entries no longer fail-open (remove them): "
            + ", ".join(stale_allowlist)
        )
    if unlisted_fail_open:
        print()
        print("FAIL: the following fail-open graders are NOT allowlisted:")
        for slug in unlisted_fail_open:
            print(f"  - {slug}")
        print()
        print(
            "A fail-open grader auto-passes on the unfixed scenario state — the "
            "lab would grade as solved without any fix. Repair the check.sh / "
            "validator so it fail-closes, or (only if genuinely tolerated) add "
            "the slug to the allowlist file."
        )
        return 1

    print("PASS: no fail-open graders outside the allowlist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
