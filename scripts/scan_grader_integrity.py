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

             It additionally enforces three ratcheted rules, because a grader can
             fail-close perfectly while grading the wrong thing entirely:
               * decorative coding graders (ceiling 0)
               * topic coherence — technology vs tasks[].validation.command (§G3)
               * checker uniqueness — identical check.sh per technology (§G1/§G4)
             The latter two have hundreds of pre-existing violations, so they gate
             on GROWTH against a recorded baseline rather than demanding zero.
--allowlist  path to a newline-delimited file of known-tolerated slugs (a frozen
             list that can only shrink). Under --check the gate ignores fail-open
             slugs that appear in the allowlist and only fails on NEW ones.

This script performs NO writes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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


# ── Coding-lab graders (§G1a) ───────────────────────────────────────────────
#
# The shell-lab classifier above reads `validation_script` / check.sh. Coding labs
# grade through `coding_spec.visible_tests` / `hidden_tests` instead, and NOT ONE of
# them has a validation_script — so every coding lab fell through to NO-MATCH and
# was counted-but-never-assessed. That is precisely where `assert callable(solution)`
# survived across 307 labs while this gate reported PASS on every PR.
#
# Classified statically rather than by execution: deterministic, fast enough for a
# PR gate, no arbitrary lab code run in CI, and — most importantly — an import error
# or missing dependency cannot masquerade as a pass.

# Assertions that hold against the SHIPPED STUB, i.e. the lab grades as solved with
# no work at all. `callable(f)` is true even when f's body raises.
_FAIL_OPEN_ASSERT_RES = [
    re.compile(r"^assert\s+callable\s*\(\s*\w+\s*\)\s*$"),
    re.compile(r"^assert\s+\w+\s+is\s+not\s+None\s*$"),      # the function object
    re.compile(r"^assert\s+True\s*$"),
    re.compile(r"^assert\s+hasattr\s*\([^)]*\)\s*$"),
    re.compile(r"^pass$"),
]

# Assertions that DO call the entrypoint but accept any non-empty answer, so a
# one-line stub (`return 1`) passes a lab whose brief is a multi-paragraph incident.
_DECORATIVE_ASSERT_RES = [
    re.compile(r"^assert\s+\w+\s*\(\s*\)\s+is\s+not\s+None\s*$"),
    re.compile(r"^assert\s+\w+\s*\(\s*\)\s*!=\s*None\s*$"),
    re.compile(r"^assert\s+\w+\s*\(\s*\)\s*$"),              # truthy return
]

_PLACEHOLDER_TEST_NAMES = {"placeholder", "placeholder_hidden"}

# Frozen ceiling for decorative coding graders — a ratchet, not a target. Lower it as
# real graders land; never raise it. (§G1)
#
# Measured baseline 2026-08-07, prompt labs excluded: 1184 coding labs ->
# 877 CODING-GRADED, 307 CODING-DECORATIVE, 0 CODING-FAIL-OPEN, 0 CODING-NO-TESTS.
# The 307 are the labs whose only tests are still named `placeholder`; they no longer
# auto-pass the shipped stub (that hole is closed) but any trivial `return 1` passes.
_CODING_DECORATIVE_CEILING = 0


def _classify_assertion(code: str) -> str:
    """'fail-open' | 'decorative' | 'graded' for one test body."""
    body = (code or "").strip()
    if not body:
        return "fail-open"
    # Multi-statement bodies are doing real work; judge only single-line graders.
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if len(lines) != 1:
        return "graded"
    line = lines[0]
    for rx in _FAIL_OPEN_ASSERT_RES:
        if rx.match(line):
            return "fail-open"
    for rx in _DECORATIVE_ASSERT_RES:
        if rx.match(line):
            return "decorative"
    return "graded"


def classify_coding(spec: dict) -> tuple[str, str]:
    """Classify a coding lab's grader. Conservative: anything not provably weak is
    reported as GRADED, so the gate does not manufacture false alarms."""
    tests = list(spec.get("visible_tests") or []) + list(spec.get("hidden_tests") or [])
    if not tests:
        return "CODING-NO-TESTS", "no visible_tests and no hidden_tests"

    verdicts = [_classify_assertion(t.get("code", "")) for t in tests]
    names = {(t.get("name") or "").strip().lower() for t in tests}
    placeholder = bool(names & _PLACEHOLDER_TEST_NAMES)
    detail = f"{len(tests)} test(s); " + ", ".join(sorted(set(verdicts)))
    if placeholder:
        detail += "; test still named 'placeholder'"

    # Fail-open only when EVERY test passes the untouched stub.
    if all(v == "fail-open" for v in verdicts):
        return "CODING-FAIL-OPEN", detail
    # Decorative when nothing meaningfully constrains the answer.
    if all(v in ("fail-open", "decorative") for v in verdicts):
        return "CODING-DECORATIVE", detail
    return "CODING-GRADED", detail


def _iter_coding_from_fs():
    """Yield (slug, technology, coding_spec) for every coding-mode scenario."""
    import yaml

    root = scenarios_root()
    rows = []
    if not root.is_dir():
        return rows
    for tech_dir in sorted(root.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name == "shared":
            continue
        for sd in sorted(tech_dir.iterdir()):
            y = sd / "scenario.yaml"
            if not sd.is_dir() or not y.is_file():
                continue
            try:
                data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            # Unpublished labs are not shipped, cannot be started and cannot award
            # XP, so they do not count against the decorative ratchet (audit §G1).
            # They still live in the repo awaiting real content.
            if data.get("is_active", True) is False:
                continue
            spec = data.get("coding_spec") or {}
            if not data.get("coding_mode") and not spec:
                continue
            # `kind: prompt` labs are graded by the Prompt Playground, not by these
            # tests — ValidateLabView short-circuits them before run_validation. Many
            # still carry a vestigial `assert True` in hidden_tests that is never
            # executed, so judging them here would be 150 false positives.
            if (spec.get("kind") or "").strip().lower() == "prompt":
                continue
            rows.append((
                data.get("slug") or sd.name,
                data.get("technology") or tech_dir.name,
                spec,
            ))
    return rows


# ── Topic coherence (§G3/§G7) ───────────────────────────────────────────────
#
# A scenario whose `technology` is grafana but whose only grading command is
# `systemctl is-active rsyslog` does not grade its own subject. The lab can be
# "solved" without touching Grafana at all. The fail-open scanner above cannot
# see this: rsyslog IS down on the unfixed state, so the grader fail-CLOSES
# correctly and passes the gate while grading the wrong thing entirely.
#
# The naive form of this rule (substring of the technology slug appears in the
# command) is unusable: measured over the tree it flags 1314 of 1851 scenarios,
# and the large majority are correct — `nvidia-smi` is the right way to grade a
# `gpu` lab, `systemctl is-active sshd` is the right way to grade an ssh-hardening
# `security` lab, and neither shares a substring with its technology slug. So the
# rule matches against a per-technology vocabulary: the slug's own words PLUS the
# tools that legitimately grade that technology. With the map below the residual
# is 438, and the residual is dominated by genuinely mis-topiced families
# (grafana graded by rsyslog, prometheus and ai-ml by nginx).
#
# Only technologies with an entry here are judged. An unmapped technology is
# skipped rather than assumed-incoherent — a missing map entry must not manufacture
# a CI failure for a technology nobody has characterised yet.
_TECH_GRADING_VOCAB: dict[str, set[str]] = {
    "gpu": {"nvidia", "cuda", "dcgm", "nccl", "nvml", "rocm"},
    "grafana": {"grafana", "datasource", "dashboard", "loki"},
    "prometheus": {"prometheus", "promtool", "node_exporter", "alertmanager", "scrape"},
    "ai-ml": {"model", "torch", "tensorflow", "triton", "mlflow", "inference",
              "ollama", "vllm", "jupyter", "python", "conda"},
    # No bare "r" (the R language): a one-letter token is a substring of virtually
    # every command and would rule the whole family coherent by accident.
    "data-science": {"python", "jupyter", "pandas", "numpy", "conda", "notebook",
                     "rstudio", "scipy", "sklearn"},
    # Deliberately NOT "sql": it is a substring of "postgresql", so including it
    # would rule the 100 `sqlite` labs graded by `systemctl is-active postgresql`
    # coherent — the exact family this rule exists to catch.
    "sqlite": {"sqlite", "sqlite3", ".db"},
    "database": {"psql", "postgres", "pg_isready", "mysql", "mariadb", "mysqld",
                 "mongod", "mongo", "redis", "sqlite3", "oracle", "cassandra",
                 "clickhouse", "elasticsearch", "influxd", "etcd", "couchdb",
                 "neo4j", "mssql", "db2"},
    "docker": {"docker", "dockerd", "containerd", "podman", "compose"},
    # "ss" is deliberately omitted here and below: it is a substring of "sshd", so
    # it would rule any ssh-graded lab coherent for a network/scanning technology.
    # Matches nothing in the tree today; excluded so it cannot start to.
    "nmap": {"nmap", "ncat", "netcat", "netstat", "ss -"},
    "security": {"ssh", "sshd", "firewall", "selinux", "sestatus", "audit",
                 "auditd", "fail2ban", "iptables", "nft", "gpg", "openssl",
                 "clamav", "aide", "sudo", "pam", "chage", "umask"},
    # "ip " / "ss -" carry their argument separator so the two-letter commands
    # cannot match inside unrelated words ("ip" alone is a substring of "script").
    "networking": {"ip ", "ping", "named", "bind", "dhcp", "nmcli", "route",
                   "bgp", "frr", "chrony", "ntp", "resolv", "ss -", "netstat",
                   "firewall", "dns", "bond", "vlan", "tcpdump", "ethtool"},
    "devops": {"git", "gitlab", "jenkins", "ansible", "helm", "docker",
               "kubectl", "runner", "pipeline", "terraform", "argocd", "vault",
               "nexus", "artifactory"},
    "rhel-linux": {"systemctl", "rpm", "dnf", "yum", "subscription-manager",
                   "selinux", "sestatus", "firewall", "journalctl", "chrony",
                   "rsyslog", "sshd", "crond", "auditd", "systemd", "lvm",
                   "mount", "grub", "tuned", "podman"},
    "linux": {"systemctl", "journalctl", "chrony", "rsyslog", "sshd", "crond",
              "systemd", "mount", "getfacl", "setfacl", "chmod", "chown",
              "lvm", "grub", "firewall", "selinux", "sestatus"},
}

# Frozen ceiling for topic-incoherent scenarios — a ratchet, not a target. Lower it
# as families are re-topiced; never raise it. Measured 2026-08-09 over the tree:
# of the active scenarios carrying a tasks[].validation.command, 1407 have a mapped
# technology and 617 of those are incoherent. Shipping this as a hard zero-tolerance
# gate would redden the build on 617 pre-existing scenarios at once, so it ratchets
# like the decorative coding ceiling does.
#
# The 617 are concentrated in whole families that grade a service they never touch:
# data-science 100 / grafana 100 / prometheus 100 / sqlite 100 / ai-ml 99 (nginx or
# rsyslog), networking 61, devops 43. Fixing a family drops this by ~100 at a stroke.
_TOPIC_INCOHERENT_CEILING = 617


def _tech_vocabulary(technology: str) -> set[str] | None:
    """Grading vocabulary for a technology, or None if the technology is unmapped.

    The vocabulary is always the slug's own words plus any curated synonyms, so a
    scenario graded by a command naming its own technology is coherent for free.
    """
    tech = (technology or "").strip().lower()
    if not tech:
        return None
    extra = _TECH_GRADING_VOCAB.get(tech)
    if extra is None:
        return None
    # Slug fragments shorter than 3 chars are dropped: splitting "ai-ml" yields
    # "ai" and "ml", which appear inside unrelated words ("ai" in "chain",
    # "mail") and would rule the family coherent by accident. The curated
    # synonyms carry the real signal for those technologies.
    words = {w for w in re.split(r"[^a-z0-9]+", tech) if len(w) > 2}
    return words | extra


def is_topic_coherent(technology: str, commands: list[str]) -> bool | None:
    """True/False if the technology is mapped, None if it cannot be judged.

    None (unmapped technology, or no validation command at all) means "not
    assessed" — never counted as a failure.
    """
    vocab = _tech_vocabulary(technology)
    if vocab is None:
        return None
    blob = " ".join(c for c in commands if c).lower()
    if not blob.strip():
        return None
    return any(word in blob for word in vocab)


def _iter_topics_from_fs():
    """Yield (slug, technology, [validation commands]) for filesystem scenarios."""
    import yaml

    root = scenarios_root()
    rows = []
    if not root.is_dir():
        return rows
    for tech_dir in sorted(root.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name == "shared":
            continue
        for sd in sorted(tech_dir.iterdir()):
            y = sd / "scenario.yaml"
            if not sd.is_dir() or not y.is_file():
                continue
            try:
                data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            if data.get("is_active", True) is False:
                continue
            commands = []
            for task in data.get("tasks") or []:
                cmd = ((task or {}).get("validation") or {}).get("command")
                if cmd:
                    commands.append(str(cmd))
            if not commands:
                continue
            rows.append((
                data.get("slug") or sd.name,
                data.get("technology") or tech_dir.name,
                commands,
            ))
    return rows


# ── Checker uniqueness (§G1/§G4/§G7) ────────────────────────────────────────
#
# aws ships 420 academy labs behind ONE byte-identical check.sh. Whatever that
# checker asserts, 419 of those labs are not graded on their own subject. The
# fail-open scanner cannot see this either: the shared checker fail-closes, so
# every one of the 420 passes the gate.
#
# Shared checkers are however legitimate by design in places —
# simulation/validation.py routes families of slugs to CANONICAL_*_CHECK
# constants deliberately — and several of the worst offenders (aws, windows,
# nmap, vmware, peoplesoft) route to a dedicated engine validator at runtime,
# which means their check.sh is not even the thing doing the grading. So this is
# a per-technology ratchet against a recorded baseline, not a hard rule.
#
# IMPORTANT LIMITATION, recorded so nobody mistakes green for graded: the rule
# hashes file bytes. Cosmetically perturbing the 420 identical files (a differing
# comment or echo string per lab) would satisfy it without changing grading at
# all. It is a floor against NEW duplication, not evidence that grading is real.
# The real signal for aws remains the dedicated-validator scan above.
#
# Measured 2026-08-09: 7086 check.sh files; largest identical group per technology
# is aws=420, html=150, openstack=149, gcp=147, azure=147, then a long 100-file
# plateau. The baseline below records each technology's largest group at that
# measurement; the gate fails when any technology EXCEEDS its recorded number, or
# when an unrecorded technology crosses _DUPE_GROUP_DEFAULT_MAX.
_DUPE_GROUP_DEFAULT_MAX = 25

_DUPE_GROUP_BASELINE: dict[str, int] = {
    "aws": 420,
    "html": 150,
    "openstack": 149,
    "gcp": 147,
    "azure": 147,
    "sqlite": 100,
    "shell-script": 100,
    "react": 100,
    "prompt-engineering": 100,
    "prometheus": 100,
    "postgresql": 100,
    "peoplesoft": 100,
    "nodejs": 100,
    "nmap": 100,
    "mysql": 100,
    "javascript": 100,
    "java": 100,
    "grafana": 100,
    "data-science": 100,
    "gpu": 99,
    "kubernetes": 95,
    "windows": 94,
    "baremetal": 94,
    "wireshark": 91,
    "vmware": 90,
    "ai-ml": 90,
    "docker": 88,
    "ansible": 84,
    "python": 84,
    "devops": 59,
    "linux": 57,
    "dellemc": 53,
    "datacenter": 51,
    "netapp": 50,
    "opentelemetry": 43,
    "soc": 43,
    "service-mesh": 39,
    "devsecops-supplychain": 38,
    "database": 35,
    "rhel-linux": 32,
    "security": 32,
}


def duplicate_checker_groups(root: Path | None = None) -> dict[str, tuple[int, str]]:
    """Largest identical-check.sh group per technology.

    Returns {technology: (group_size, digest)}. Hashes the normalised bytes so
    trailing-whitespace churn does not read as a new checker.
    """
    import hashlib

    base = root or scenarios_root()
    per_tech: dict[str, Counter] = defaultdict(Counter)
    if not base.is_dir():
        return {}
    for tech_dir in sorted(base.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name == "shared":
            continue
        for sd in sorted(tech_dir.iterdir()):
            check = sd / "check.sh"
            if not sd.is_dir() or not check.is_file():
                continue
            try:
                text = check.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            norm = "\n".join(line.rstrip() for line in text.splitlines()).strip()
            per_tech[tech_dir.name][hashlib.sha256(norm.encode()).hexdigest()] += 1
    out: dict[str, tuple[int, str]] = {}
    for tech, counter in per_tech.items():
        if not counter:
            continue
        digest, size = counter.most_common(1)[0]
        out[tech] = (size, digest)
    return out


def duplicate_checker_regressions(
    groups: dict[str, tuple[int, str]],
    baseline: dict[str, int] | None = None,
    default_max: int = _DUPE_GROUP_DEFAULT_MAX,
) -> list[tuple[str, int, int]]:
    """[(technology, observed, allowed)] for technologies over their ceiling."""
    base = _DUPE_GROUP_BASELINE if baseline is None else baseline
    regressions = []
    for tech, (size, _digest) in sorted(groups.items()):
        allowed = base.get(tech, default_max)
        if size > allowed:
            regressions.append((tech, size, allowed))
    return regressions


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
    no_match_by_tech: Counter[str] = Counter()

    for slug, tech, sim_type, db_script in rows:
        cls, output = classify(slug, sim_type, db_script)
        classes[cls] += 1
        if cls == "NO-MATCH":
            no_match_by_tech[tech] += 1
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

    # ── Coding-lab pass (§G1a) ──────────────────────────────────────────────
    coding_classes: Counter[str] = Counter()
    coding_fail_open: list[str] = []
    coding_decorative: list[str] = []
    coding_by_tech: Counter[str] = Counter()
    for slug, tech, spec in _iter_coding_from_fs():
        ccls, cdetail = classify_coding(spec)
        coding_classes[ccls] += 1
        if ccls == "CODING-FAIL-OPEN":
            coding_fail_open.append(slug)
            coding_by_tech[tech] += 1
        elif ccls in ("CODING-DECORATIVE", "CODING-NO-TESTS"):
            coding_decorative.append(slug)
            coding_by_tech[tech] += 1

    # ── Topic-coherence pass (§G3) ──────────────────────────────────────────
    topic_incoherent: list[tuple[str, str, str]] = []
    topic_by_tech: Counter[str] = Counter()
    topic_assessed = 0
    for slug, tech, commands in _iter_topics_from_fs():
        verdict = is_topic_coherent(tech, commands)
        if verdict is None:
            continue
        topic_assessed += 1
        if not verdict:
            topic_incoherent.append((slug, tech, commands[0][:100]))
            topic_by_tech[tech] += 1

    # ── Checker-uniqueness pass (§G1/§G4) ───────────────────────────────────
    dupe_groups = duplicate_checker_groups()
    dupe_regressions = duplicate_checker_regressions(dupe_groups)

    total = sum(classes.values())
    print("=" * 72)
    print(f"GRADER-INTEGRITY SCAN  (source: {source})")
    print("=" * 72)
    print(f"Scenarios scanned : {total}")
    for cls in ("FAIL-OPEN", "NO-MATCH", "FAIL-CLOSED", "ERROR"):
        if classes.get(cls):
            print(f"  {cls:<12}: {classes[cls]}")
    # NO-MATCH means "not evaluated", not "passed". Printing it silently beside a
    # PASS is how 1204 unassessed scenarios read as covered. (§G1b)
    no_match = classes.get("NO-MATCH", 0)
    if no_match:
        pct = (100.0 * no_match) / total if total else 0.0
        print(
            f"  NOTE: {no_match} ({pct:.1f}%) scenarios were NOT EVALUATED by the "
            "shell-lab classifier (no validation check matched). This is not a pass."
        )
        for tech, cnt in no_match_by_tech.most_common(10):
            print(f"        not evaluated — {tech:<18}: {cnt}")
    print()

    if coding_classes:
        ctotal = sum(coding_classes.values())
        print("CODING-LAB GRADERS  (coding_spec tests, not validation_script)")
        print("-" * 40)
        print(f"  scanned          : {ctotal}")
        for cls in ("CODING-FAIL-OPEN", "CODING-DECORATIVE", "CODING-NO-TESTS",
                    "CODING-GRADED"):
            if coding_classes.get(cls):
                print(f"  {cls:<18}: {coding_classes[cls]}")
        if coding_by_tech:
            print("  weakest by technology:")
            for tech, cnt in coding_by_tech.most_common(10):
                print(f"    {tech:<18}: {cnt}")
        print()

    if topic_assessed:
        print("TOPIC COHERENCE  (technology vs tasks[].validation.command)")
        print("-" * 40)
        print(f"  assessed         : {topic_assessed}"
              f"  (technologies with a grading vocabulary)")
        print(f"  incoherent       : {len(topic_incoherent)}"
              f"  (ceiling {_TOPIC_INCOHERENT_CEILING})")
        for tech, cnt in topic_by_tech.most_common(10):
            print(f"    {tech:<18}: {cnt}")
        print()

    if dupe_groups:
        print("CHECKER UNIQUENESS  (largest identical check.sh group per technology)")
        print("-" * 40)
        for tech, (size, _d) in sorted(dupe_groups.items(), key=lambda kv: -kv[1][0])[:10]:
            allowed = _DUPE_GROUP_BASELINE.get(tech, _DUPE_GROUP_DEFAULT_MAX)
            flag = "  <-- OVER" if size > allowed else ""
            print(f"    {tech:<18}: {size:>4}  (allowed {allowed}){flag}")
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
        "not_evaluated_count": classes.get("NO-MATCH", 0),
        "not_evaluated_by_technology": dict(no_match_by_tech.most_common()),
        "topic_coherence": {
            "assessed": topic_assessed,
            "incoherent_count": len(topic_incoherent),
            "ceiling": _TOPIC_INCOHERENT_CEILING,
            "incoherent_by_technology": dict(topic_by_tech.most_common()),
            "examples": [
                {"slug": s, "technology": t, "command": c}
                for s, t, c in topic_incoherent[:20]
            ],
        },
        "checker_uniqueness": {
            "largest_group_by_technology": {
                t: size for t, (size, _d) in sorted(
                    dupe_groups.items(), key=lambda kv: -kv[1][0]
                )
            },
            "regressions": [
                {"technology": t, "observed": o, "allowed": a}
                for t, o, a in dupe_regressions
            ],
        },
        "coding": {
            "counts": dict(coding_classes),
            "fail_open_slugs": sorted(coding_fail_open),
            "decorative_slugs": sorted(coding_decorative),
            "weakest_by_technology": dict(coding_by_tech.most_common()),
        },
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
    # Coding labs are gated too, against their own frozen ceiling. Without this the
    # gate reported PASS while 307 coding labs graded on `assert callable(solution)`.
    unlisted_coding_fail_open = sorted(s for s in coding_fail_open if s not in allowlist)
    n_decorative = len(coding_decorative)
    print(f"Coding fail-open           : {len(coding_fail_open)}"
          f" ({len(unlisted_coding_fail_open)} not allowlisted)")
    print(f"Coding decorative          : {n_decorative}"
          f"  (ceiling {_CODING_DECORATIVE_CEILING})")

    failed = False
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
        failed = True

    if unlisted_coding_fail_open:
        print()
        print("FAIL: coding labs whose tests pass the SHIPPED STUB:")
        for slug in unlisted_coding_fail_open[:40]:
            print(f"  - {slug}")
        if len(unlisted_coding_fail_open) > 40:
            print(f"  ... and {len(unlisted_coding_fail_open) - 40} more")
        print()
        print(
            "These grade as solved with no work at all (e.g. `assert "
            "callable(solution)` is true even when the stub raises). Write a test "
            "that constrains the answer."
        )
        failed = True

    # Decorative graders are a large pre-existing debt (§G1), so they are ratcheted
    # rather than hard-failed: the count may shrink, never grow.
    if n_decorative > _CODING_DECORATIVE_CEILING:
        print()
        print(
            f"FAIL: decorative coding graders grew to {n_decorative}, ceiling is "
            f"{_CODING_DECORATIVE_CEILING}. A test that any trivial stub satisfies "
            "(`assert solution() is not None`) does not grade the lab's subject. "
            "Lower the ceiling as these are fixed; never raise it."
        )
        failed = True
    elif n_decorative < _CODING_DECORATIVE_CEILING:
        print(
            f"NOTE: decorative coding graders down to {n_decorative} — lower "
            f"_CODING_DECORATIVE_CEILING to {n_decorative} to lock the gain in."
        )

    # Topic coherence: ratcheted like the decorative ceiling. A lab graded on a
    # service unrelated to its own technology fail-CLOSES correctly and so is
    # invisible to every check above it.
    n_incoherent = len(topic_incoherent)
    print(f"Topic-incoherent scenarios : {n_incoherent}"
          f"  (ceiling {_TOPIC_INCOHERENT_CEILING})")
    if n_incoherent > _TOPIC_INCOHERENT_CEILING:
        print()
        print(
            f"FAIL: topic-incoherent scenarios grew to {n_incoherent}, ceiling is "
            f"{_TOPIC_INCOHERENT_CEILING}. These grade a service unrelated to their "
            "own technology, so the lab can be solved without touching its subject:"
        )
        for slug, tech, cmd in topic_incoherent[:40]:
            print(f"  - {slug}  [{tech}]  -> {cmd}")
        if n_incoherent > 40:
            print(f"  ... and {n_incoherent - 40} more")
        print(
            "Point validation.command at the technology under test, or (if the "
            "command is legitimate for this technology) extend _TECH_GRADING_VOCAB."
        )
        failed = True
    elif n_incoherent < _TOPIC_INCOHERENT_CEILING:
        print(
            f"NOTE: topic-incoherent scenarios down to {n_incoherent} — lower "
            f"_TOPIC_INCOHERENT_CEILING to {n_incoherent} to lock the gain in."
        )

    # Checker uniqueness: per-technology ratchet against the recorded baseline.
    print(f"Checker-dupe regressions   : {len(dupe_regressions)}")
    if dupe_regressions:
        print()
        print("FAIL: these technologies grew their largest identical-check.sh group:")
        for tech, observed, allowed in dupe_regressions:
            print(f"  - {tech}: {observed} scenarios share one check.sh (allowed {allowed})")
        print(
            "N scenarios behind one byte-identical checker means N-1 of them are "
            "not graded on their own subject. Author a real check.sh for the new "
            "labs. Do NOT satisfy this by cosmetically perturbing the duplicates — "
            "the rule hashes file bytes and would go green with grading unchanged."
        )
        failed = True

    if failed:
        return 1

    print("PASS: no fail-open graders outside the allowlist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
