"""
Module expansion — subtopics, notes, checklists, and explanations for every lesson.

Ensures no module ships thin content; every section gets topic-specific detail.
"""

from __future__ import annotations

import re

from .topic_profiles import get_profile

# Universal subtopic templates per section (title template, explanation template)
SECTION_SUBTOPIC_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "theory": [
        ("What this module covers", "{module} is essential {topic} knowledge. You will learn the vocabulary, mental models, and production context needed before hands-on work."),
        ("Why operators care", "Mistakes in {module_lower} cause outages, data loss, or security incidents. Teams document runbooks because on-call engineers must act without guessing."),
        ("Prerequisites", "Comfort with adjacent {topic} basics. Review prior modules in this course if terms like control plane, state, or SLO are unfamiliar."),
        ("Production context", "Enterprise {topic} environments enforce change control, audit trails, and rollback plans. Every concept here maps to a real ticket or design review question."),
        ("Common misconceptions", "Tutorial labs simplify topology — production adds replication lag, certificate expiry, and noisy neighbors. Plan for partial failure."),
        ("How to study this module", "Read theory first, sketch architecture, run labs twice (break/fix/verify), then answer interview questions aloud."),
    ],
    "architecture": [
        ("Control plane vs data plane", "Configuration and orchestration (control) vs traffic and payload processing (data). Know which plane your change affects."),
        ("Core components", "List every daemon, service, or API involved in {module_lower}. Missing one component in a diagram hides a failure domain."),
        ("Data flow", "Trace a request or transaction end-to-end through {module_lower}. Note sync vs async steps and persistence points."),
        ("Dependencies", "{module} depends on network, DNS, TLS, identity, storage, and observability. A green health check on one layer does not imply the stack is healthy."),
        ("Scaling model", "Horizontal vs vertical scaling for {module_lower}. Identify stateful vs stateless parts — state complicates failover."),
        ("Failure domains", "Single host, AZ, region, or control plane outage — document expected behavior and manual failover steps."),
    ],
    "concepts": [
        ("Terminology", "Define every acronym you use in {module_lower} runbooks. Ambiguous terms cause wrong fixes under pressure."),
        ("Lifecycle", "Create → configure → operate → upgrade → decommission. Automate transitions where possible."),
        ("State and idempotency", "Repeating the same {topic} operation should be safe. Know which commands are additive vs destructive."),
        ("Consistency models", "Strong vs eventual consistency affects {module_lower} during partitions and failover."),
        ("Blast radius", "If {module_lower} fails, which services and users are affected within 5 minutes?"),
        ("Versioning and compatibility", "Pin versions in {topic}; read release notes before upgrades."),
    ],
    "use_cases": [
        ("Greenfield deployment", "Design {module_lower} for a new product with observability and security from day one."),
        ("Migration", "Move legacy workloads to {module_lower} with rollback and data validation gates."),
        ("Incident recovery", "Restore {topic} service during partial outage while preserving forensic evidence."),
        ("Compliance audit", "Prove encryption, access control, and retention for {module_lower} with automated evidence."),
        ("Cost optimization", "Right-size {module_lower} using utilization metrics without breaching SLOs."),
        ("Capacity planning", "Forecast growth for {module_lower}; load-test before peak events."),
    ],
    "labs": [
        ("Objective", "Complete hands-on tasks for {module} in the {topic} playground or linked FixitLab scenario."),
        ("Setup", "Open terminal/simulator, confirm identity/context, snapshot baseline metrics."),
        ("Exercise steps", "Reproduce issue → diagnose → apply fix → validate → document runbook entry."),
        ("Validation", "Use Check Solution, health endpoints, or peer checklist before marking done."),
        ("Stretch goals", "Break the system intentionally and recover twice to build muscle memory."),
        ("Lab hygiene", "Never use production credentials in training; use synthetic data only."),
    ],
    "simulations": [
        ("Simulator access", "Open {topic} simulator from FixitLab lab toolbar (Terraform, Grafana, VMware, Windows, AWX, etc.)."),
        ("What to compare", "Match simulated logs, metrics, and UI labels to production expectations."),
        ("Grading model", "Real simulator state checks and API checks — treat sim like staging."),
        ("Cross-tech labs", "Some scenarios link terminal fixes to GUI simulator state."),
        ("Repeatability", "Run break/fix cycle three times until steps are automatic."),
    ],
    "projects": [
        ("Scope", "End-to-end {module_lower} implementation in sandbox with IaC and CI gate."),
        ("Deliverables", "Architecture diagram, repo link, dashboard, rollback doc, handoff checklist."),
        ("Acceptance", "SLO defined, alerts wired, security review complete."),
        ("Timeline", "Split into milestones: design → implement → test → document."),
    ],
    "troubleshooting": [
        ("Symptom triage", "Scope user impact, error rate, and start time of {module_lower} degradation."),
        ("Log sources", "Collect application, system, and audit logs before restart."),
        ("Metrics", "Check latency, saturation, errors, and {topic}-specific signals (lag, queue depth)."),
        ("Recent changes", "Correlate with deploys, config pushes, cert rotations, or traffic shifts."),
        ("Mitigation", "Rollback, scale, failover, or feature flag — pick fastest safe option."),
        ("Verification", "Confirm SLO green and notify stakeholders before closing incident."),
    ],
    "interview": [
        ("Explain simply", "Describe {module_lower} in two minutes to a junior engineer."),
        ("Scale question", "What breaks first at 10× and 100× load for {module_lower}?"),
        ("Rollback story", "Walk through a safe rollback after a bad {topic} change."),
        ("Trade-offs", "Managed vs self-hosted, cost vs reliability, speed vs safety."),
        ("Metrics", "Which SLIs prove {module_lower} is healthy?"),
    ],
    "scenario": [
        ("On-call prompt", "{module} degraded — error spike 15 minutes ago. First 15 minutes?"),
        ("Communication", "Status page, internal channel, executive summary if customer-facing."),
        ("Escalation", "When to escalate to platform, security, or vendor support."),
        ("Evidence", "Preserve logs and timelines for postmortem."),
    ],
    "assessment": [
        ("Self-check rubric", "Rate 1–5: explain, execute, troubleshoot, teach, defend to security."),
        ("Retake criteria", "Score below 4 → repeat labs and simulations."),
        ("Cert alignment", "Map weak areas to FixitLab certification objectives."),
    ],
    "certification": [
        ("Exam objectives", "Cross-reference {module_lower} with vendor cert blueprints."),
        ("Practice", "Timed labs and scenario questions under exam conditions."),
        ("Domains", "Focus troubleshooting and security — heavily weighted on practical exams."),
    ],
    "enterprise": [
        ("Change control", "CAB approval, maintenance windows, and emergency break-glass."),
        ("Multi-region", "Active/active or active/passive patterns for {module_lower}."),
        ("Audit", "SOC2/ISO evidence from logs and access reviews."),
        ("DR drills", "Quarterly restore/failover with measured RTO/RPO."),
    ],
    "best_practices": [
        ("Automation", "GitOps/IaC for {module_lower}; no snowflake servers."),
        ("Small batches", "Frequent small deploys beat rare big-bang releases."),
        ("Golden paths", "Make the secure path the easiest path."),
        ("Documentation", "Runbooks updated after every incident."),
    ],
    "security": [
        ("Least privilege", "Narrow IAM/RBAC for {module_lower} operators and service accounts."),
        ("Encryption", "TLS in transit, KMS at rest, rotate keys on schedule."),
        ("Secrets", "Vault/sealed secrets — never in Git or shell history."),
        ("Supply chain", "Signed images, SBOM, dependency scanning in CI."),
    ],
    "performance": [
        ("Baselines", "Capture CPU, memory, I/O, p99 latency before tuning {module_lower}."),
        ("Profiling", "Profile under realistic load; change one variable at a time."),
        ("Capacity", "Headroom for failover (N+1, multi-AZ)."),
    ],
    "monitoring": [
        ("SLIs and SLOs", "Define measurable SLIs for {module_lower}; set SLO targets and error budgets."),
        ("Dashboards", "Answer: healthy? if not, why?"),
        ("Alerting", "Actionable pages only — every alert links to runbook."),
    ],
    "incidents": [
        ("Postmortem study", "Review public {topic} outages — detection, containment, prevention."),
        ("Signals missed", "What monitor would have caught the issue earlier?"),
    ],
    "rca": [
        ("Timeline", "UTC timestamps from first symptom to resolution."),
        ("Contributing factors", "Multiple causes — avoid single-root oversimplification."),
        ("Actions", "Corrective (now) vs preventive (stop recurrence)."),
        ("Verification", "Prove fix holds under load; update monitors and runbooks."),
    ],
    "notes": [
        ("Key takeaways", "Summarize {module}: top three facts to remember for on-call."),
        ("Quick reference", "Commands, ports, and config paths for {module_lower}."),
        ("Warnings", "Destructive operations require backup and ticket linkage."),
        ("Further reading", "Official {topic} docs, FixitLab labs, next module in course."),
        ("Study checklist", "□ Read □ Diagram □ Lab □ Interview Q □ Assessment"),
    ],
}


def _fill(template: str, topic: str, module: str) -> str:
    return template.format(
        topic=topic,
        module=module,
        module_lower=module.lower(),
    )


def expand_subtopics(topic: str, module: str, section_key: str) -> list[tuple[str, str]]:
    """Return (title, explanation) pairs for a section."""
    templates = SECTION_SUBTOPIC_TEMPLATES.get(section_key, SECTION_SUBTOPIC_TEMPLATES["theory"])
    items = [(_fill(title, topic, module), _fill(body, topic, module)) for title, body in templates]

    profile = get_profile(topic)
    for key, text in (profile.get("concepts") or {}).items():
        key_norm = key.lower().replace("_", " ")
        if any(w in module.lower() for w in key_norm.split()) or key_norm in module.lower():
            items.append((key.replace("_", " ").title(), text))

    # Split module title into phrase-based subtopics
    parts = re.split(r"[,/&]+|\band\b", module, flags=re.I)
    for part in parts:
        part = part.strip()
        if len(part) > 4 and part.lower() != module.lower():
            items.append((
                part,
                f"**{part}** in {topic}: understand purpose, configuration, failure modes, and monitoring for production {part.lower()}.",
            ))

    return items[:20]  # cap per section


def format_subtopics_block(items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    lines = ["**Topics covered in this section:**", ""]
    for title, body in items:
        lines.append(f"- **{title}** — {body}")
    lines.append("")
    lines.append(
        "**Explanation:** Each bullet is a subtopic you should understand end-to-end. "
        "If you cannot explain it aloud in one minute, re-read and run the lab again."
    )
    return "\n".join(lines)


def format_notes_block(topic: str, module: str, level: str) -> str:
    return (
        f"\n\n---\n\n"
        f"**📝 Notes ({level} track)**\n\n"
        f"- Bookmark official {topic} documentation for {module.lower()}.\n"
        f"- Copy commands into your personal runbook — do not rely on memory under stress.\n"
        f"- Pair this module with FixitLab hands-on labs and certification assessments.\n"
        f"- Revisit after 48 hours (spaced repetition) to lock in concepts.\n"
        f"- If anything is unclear, repeat the lab before advancing to the next module."
    )


def get_module_checklist(topic: str, module: str) -> str:
    return (
        f"**End-of-module checklist for {module}:**\n\n"
        f"1. □ I can explain the theory without reading notes\n"
        f"2. □ I drew the architecture and labeled failure domains\n"
        f"3. □ I completed hands-on labs or simulation\n"
        f"4. □ I answered scenario and interview questions aloud\n"
        f"5. □ I documented commands and warnings in my runbook\n"
        f"6. □ I am ready for the next {topic} module"
    )
