"""
End-to-end tutorial section writers — multi-paragraph lessons per module.

Produces prose comparable to hand-authored tutorials_extra.json entries.
"""

from __future__ import annotations

import re

from .book_chapter import get_book_body
from .module_expansion import (
    expand_subtopics,
    format_notes_block,
    format_subtopics_block,
    get_module_checklist,
)
from .topic_profiles import get_profile

LEVEL_LABELS = {
    "beginner": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
    "expert": "Expert",
    "enterprise": "Real Enterprise",
}

SECTION_HEADINGS: list[tuple[str, str]] = [
    ("Theory", "theory"),
    ("Architecture", "architecture"),
    ("Core concepts", "concepts"),
    ("Use cases", "use_cases"),
    ("Hands-on labs", "labs"),
    ("Interactive simulations", "simulations"),
    ("Projects", "projects"),
    ("Troubleshooting", "troubleshooting"),
    ("Interview questions", "interview"),
    ("Scenario questions", "scenario"),
    ("Assessments", "assessment"),
    ("Certification exam prep", "certification"),
    ("Enterprise production examples", "enterprise"),
    ("Best practices", "best_practices"),
    ("Security practices", "security"),
    ("Performance tuning", "performance"),
    ("Monitoring", "monitoring"),
    ("Real incidents", "incidents"),
    ("Root cause analysis", "rca"),
    ("Notes and key takeaways", "notes"),
]


def _kw(module: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-zA-Z0-9]+", module) if len(w) > 2}


def _match_concepts(profile: dict, module: str) -> list[str]:
    concepts = profile.get("concepts") or {}
    if not concepts:
        return []
    keys = _kw(module)
    matched = []
    for key, text in concepts.items():
        parts = set(key.lower().replace("_", " ").split())
        if keys & parts or any(p in module.lower() for p in parts):
            matched.append(f"**{key.replace('_', ' ').title()}:** {text}")
    if not matched:
        matched = [f"**{k.replace('_', ' ').title()}:** {v}" for k, v in list(concepts.items())[:4]]
    return matched


def _level_note(level: str) -> str:
    return {
        "beginner": "At this level, prioritize understanding vocabulary and safe read-only exploration before making changes.",
        "intermediate": "You should connect this module to adjacent systems (network, identity, storage) and validate in staging.",
        "advanced": "Focus on failure modes, automation, and measurable rollback plans before touching production.",
        "expert": "You are expected to lead design reviews, mentor others, and defend trade-offs with latency/cost/risk data.",
        "enterprise": "Operate under change control, audited access, contractual SLAs, and executive-visible incident comms.",
    }.get(level, "")


def _enrich(section_key: str, topic: str, module: str, level: str, body: str) -> str:
    """Append subtopics, notes, and checklist so no section is thin."""
    subtopics = expand_subtopics(topic, module, section_key)
    block = format_subtopics_block(subtopics)
    notes = format_notes_block(topic, module, level)
    if section_key == "notes":
        checklist = get_module_checklist(topic, module)
        return (
            f"## Notes and key takeaways\n\n"
            f"**Module:** {module} · **Track:** {LEVEL_LABELS.get(level, level)} · **Topic:** {topic}\n\n"
            f"{block}\n\n{checklist}{notes}"
        )
    enriched = body
    if block:
        enriched += "\n\n" + block
    if section_key in ("rca", "assessment", "certification"):
        enriched += "\n\n" + get_module_checklist(topic, module)
    enriched += notes
    return enriched


def _write_notes(topic: str, module: str, level: str, profile: dict) -> str:
    book = get_book_body(topic, module, "notes", level)
    return _enrich("notes", topic, module, level, book)


def _write_theory(topic: str, module: str, level: str, profile: dict) -> str:
    tagline = profile.get("tagline", topic)
    concepts = _match_concepts(profile, module)
    p1 = (
        f"## Theory\n\n"
        f"**{module}** is a core lesson in the **{topic}** track ({LEVEL_LABELS.get(level, level)}). "
        f"{tagline}.\n\n"
        f"In production, teams rely on this knowledge during design reviews, change windows, and on-call. "
        f"Understanding *why* a component exists prevents expensive misconfigurations that only surface under load."
    )
    p2 = (
        f"Before touching systems, map stakeholders: who owns the data, who consumes the API, "
        f"and what SLO applies. {_level_note(level)}"
    )
    body = p1 + "\n\n" + p2
    if concepts:
        body += "\n\n**Key ideas for this module:**\n\n" + "\n\n".join(concepts[:5])
    if profile.get("architecture"):
        body += f"\n\n**Platform context:** {profile['architecture']}"
    return body


def _write_architecture(topic: str, module: str, level: str, profile: dict) -> str:
    arch = profile.get("architecture", "Map control plane vs data plane and list dependencies.")
    engines = profile.get("engines") or profile.get("components") or []
    eng = ""
    if engines:
        eng = f"\n\n**Major components:** {', '.join(engines) if isinstance(engines, list) else engines}."
    diagram = (
        f"\n\n```mermaid\nflowchart LR\n"
        f"  user[User / Client] --> edge[Edge / LB]\n"
        f"  edge --> app[{module}]\n"
        f"  app --> data[(Data / State)]\n"
        f"  app --> obs[Logs & Metrics]\n```"
    )
    return (
        f"## Architecture\n\n"
        f"For **{module}**, draw a one-page diagram before implementing. Label north-south traffic (users → edge → app) "
        f"and east-west traffic (service-to-service). Mark trust boundaries where credentials rotate and where data is encrypted.\n\n"
        f"{arch}{eng}{diagram}\n\n"
        f"**Failure domains:** identify single points of failure. If one node dies, does the system degrade gracefully "
        f"or halt entirely? Document RTO (how fast you recover) and RPO (how much data you can lose) for stateful parts.\n\n"
        f"**Dependency checklist:** DNS, TLS certificates, identity (SSO/IAM), secrets store, backup target, and "
        f"monitoring endpoints. {_level_note(level)}"
    )


def _write_concepts(topic: str, module: str, level: str, profile: dict) -> str:
    items = _match_concepts(profile, module)
    extra = (
        f"\n\n**Lifecycle thinking:** every resource moves through create → configure → operate → upgrade → retire. "
        f"Idempotency means repeating the same operation yields the same result — critical for automation.\n\n"
        f"**Blast radius:** when {module.lower()} fails, list upstream/downstream services affected within five minutes."
    )
    intro = (
        f"## Core concepts\n\n"
        f"Master these terms for **{module}** before labs. You should explain each without notes at "
        f"{LEVEL_LABELS.get(level, level)} depth."
    )
    if items:
        return intro + "\n\n" + "\n\n".join(items) + extra
    return intro + extra


def _write_use_cases(topic: str, module: str, level: str, profile: dict) -> str:
    cases = [
        f"**Greenfield:** design {module.lower()} for a new product with autoscaling and observability from day one.",
        f"**Migration:** move legacy {topic.lower()} workloads with dual-write or read-replica cutover and rollback plan.",
        "**Incident recovery:** restore service during partial outage while preserving evidence for postmortem.",
        "**Compliance audit:** prove encryption, access controls, and retention policies with automated evidence.",
        "**Cost optimization:** right-size resources using utilization metrics without breaching SLOs.",
    ]
    return (
        f"## Use cases\n\n"
        f"Match each scenario to metrics (latency, error rate, saturation) and the owner who approves change.\n\n"
        + "\n\n".join(cases)
    )


def _write_labs(topic: str, module: str, level: str, profile: dict, playground: str) -> str:
    cmds = profile.get("commands") or {}
    cmd = next(iter(cmds.values()), f"# Practice {module}\nhelp | head -5")
    return (
        f"## Hands-on labs\n\n"
        f"Complete a FixitLab scenario for **{module}** using the **{topic}** playground (`{playground}`).\n\n"
        f"**Step-by-step:**\n"
        f"1. Read objectives and constraints — note what *must not* change.\n"
        f"2. Reproduce the failure or blank slate; capture baseline metrics/logs.\n"
        f"3. Apply the fix incrementally; one change at a time so you know what worked.\n"
        f"4. Validate with automated checks or peer review checklist.\n"
        f"5. Write a three-line runbook entry: symptom → cause → fix.\n\n"
        f"Use **Check Solution** when the lab grades terminal or simulator markers.\n\n"
        f"**Starter commands:**\n```\n{cmd}\n```"
    )


def _write_simulations(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Interactive simulations\n\n"
        f"FixitLab simulators let you practice **{module}** without production risk. "
        f"Open the **{topic}** simulator from the lab toolbar (Terraform Cloud, Grafana, VMware, Windows Server, AWX, etc.).\n\n"
        f"Compare simulated output to real environments: error strings, metric names, UI labels, and timing. "
        f"Simulations grade via real state checks (service status, pods, files, command output, or API validation) — treat them like a staging environment.\n\n"
        f"**Exercise:** break → fix → verify cycle three times until muscle memory forms."
    )


def _write_projects(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Projects\n\n"
        f"**Capstone:** implement **{module}** end-to-end in a sandbox.\n\n"
        f"**Deliverables:** architecture diagram, IaC/Config repo link, CI gate output, dashboard screenshot, "
        f"rollback procedure, and operator handoff doc.\n\n"
        f"**Acceptance criteria:** SLO defined, alerts wired to runbook, security review checklist complete, "
        f"on-call can execute your runbook without calling you."
    )


def _write_troubleshooting(topic: str, module: str, level: str, profile: dict) -> str:
    slo = profile.get("slo", "latency, errors, saturation, replication lag")
    return (
        f"## Troubleshooting\n\n"
        f"When **{module}** misbehaves, use this ordered playbook:\n\n"
        f"1. **Scope impact** — who is affected, severity, recent deploys.\n"
        f"2. **Collect signals** — logs, metrics ({slo}), traces, change tickets.\n"
        f"3. **Bisect changes** — correlate start time with releases or config drift.\n"
        f"4. **Validate dependencies** — DNS, TLS, credentials, disk, network ACLs.\n"
        f"5. **Mitigate** — rollback, scale, failover, or feature flag.\n"
        f"6. **Verify recovery** — SLO green, synthetic checks pass, stakeholders notified.\n\n"
        f"Never restart blindly without capturing logs — you may destroy evidence."
    )


def _write_interview(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Interview questions\n\n"
        f"Practice aloud — interviews test clarity under pressure.\n\n"
        f"- Explain **{module.lower()}** in two minutes to a junior engineer.\n"
        f"- What breaks first at 10× traffic? At 100×?\n"
        f"- How do you roll back a bad change safely?\n"
        f"- Compare managed vs self-hosted for {topic}.\n"
        f"- Which metrics prove this system is healthy?\n"
        f"- Describe a production incident you resolved involving {topic.lower()}."
    )


def _write_scenario(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Scenario questions\n\n"
        f"**Prompt:** \"{module} is degraded — error rate spiked 15 minutes ago. Walk me through your first 15 minutes.\"\n\n"
        f"**Strong answer structure:** stabilize (stop bleeding) → communicate (status page, internal channel) → "
        f"diagnose (hypothesis list) → mitigate (rollback/feature flag) → verify (SLO) → schedule postmortem.\n\n"
        f"Mention who you escalate to and what data you capture for RCA."
    )


def _write_assessment(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Assessments\n\n"
        f"Rate yourself 1–5 on each dimension (below 4 = repeat labs):\n\n"
        f"- Explain concepts without notes\n"
        f"- Execute hands-on tasks unaided\n"
        f"- Troubleshoot an unknown failure\n"
        f"- Teach a peer\n"
        f"- Defend design to security/compliance\n\n"
        f"FixitLab certification tracks provide timed assessments aligned with this module."
    )


def _write_certification(topic: str, module: str, level: str, profile: dict) -> str:
    certs = profile.get("certs", "vendor and FixitLab certification tracks")
    return (
        f"## Certification exam prep\n\n"
        f"Map **{module}** to exam objectives for: **{certs}**.\n\n"
        f"Build a study sheet: objective ID → FixitLab module → hands-on lab → mock question. "
        f"Practice under time limits. Focus on troubleshooting and security objectives — they dominate practical exams."
    )


def _write_enterprise(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Enterprise production examples\n\n"
        f"At enterprise scale, **{module}** runs with:\n\n"
        f"- Change Advisory Board approval for production\n"
        f"- Automated compliance scans (CIS, SOC2 controls)\n"
        f"- Multi-region active/passive or active/active failover\n"
        f"- Break-glass access with ticket linkage and session recording\n"
        f"- Quarterly DR exercises with measured RTO/RPO\n\n"
        f"Review sanitized runbooks from large-scale {topic.lower()} deployments."
    )


def _write_best_practices(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Best practices\n\n"
        f"- Automate **{module.lower()}** via IaC/GitOps — no snowflake servers.\n"
        f"- Keep changes small; deploy frequently with automated tests.\n"
        f"- Staging must mirror production topology (not just smaller).\n"
        f"- Document golden paths; make the easy way the secure way.\n"
        f"- Run game days to validate runbooks before real incidents."
    )


def _write_security(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Security practices\n\n"
        f"- **Least privilege** — narrow IAM/RBAC; no shared admin accounts.\n"
        f"- **Encryption** — TLS in transit; KMS at rest; rotate keys on schedule.\n"
        f"- **Secrets** — vault or sealed secrets; never in Git or shell history.\n"
        f"- **Supply chain** — signed images, SBOM, dependency scanning in CI.\n"
        f"- **Audit** — immutable logs; alert on privilege escalation.\n\n"
        f"Threat-model {module.lower()} for insider abuse and external attack paths."
    )


def _write_performance(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Performance tuning\n\n"
        f"Profile **{module}** under realistic load before tuning.\n\n"
        f"- Establish baselines: CPU, memory, I/O, network, p50/p95/p99 latency.\n"
        f"- Change one variable at a time; record before/after evidence.\n"
        f"- Watch saturation — queues form before errors spike.\n"
        f"- Capacity plan with headroom for failover (N+1 or multi-AZ).\n\n"
        f"Premature optimization wastes time; measure first."
    )


def _write_monitoring(topic: str, module: str, level: str, profile: dict) -> str:
    slo = profile.get("slo", "availability, latency, error rate, saturation")
    return (
        f"## Monitoring\n\n"
        f"Define **SLIs** (what you measure) and **SLOs** (target over window) for **{module}**.\n\n"
        f"Suggested signals: {slo}.\n\n"
        f"Dashboards must answer: \"Are we healthy?\" and \"If not, why?\" "
        f"Alerts route to runbooks — every page must be actionable. "
        f"Use multi-window burn rates for error budgets."
    )


def _write_incidents(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Real incidents\n\n"
        f"Study public postmortems involving **{topic.lower()}** (database failover, K8s control plane outage, "
        f"GPU thermal shutdown, BGP misconfiguration, etc.).\n\n"
        f"Extract: earliest detectable signal, containment action, what monitoring was missing, "
        f"and preventive controls added afterward. Apply those lessons to **{module}**."
    )


def _write_rca(topic: str, module: str, level: str, profile: dict) -> str:
    return (
        f"## Root cause analysis\n\n"
        f"After any **{module}** incident:\n\n"
        f"1. Timeline with UTC timestamps\n"
        f"2. Contributing factors (not just root cause — systems have many)\n"
        f"3. Corrective (fix now) vs preventive (stop recurrence) actions\n"
        f"4. Verification under load / chaos test\n"
        f"5. Blameless review; update runbooks and monitors\n\n"
        f"Close the loop when alerts fire less often and MTTR drops."
    )


_WRITERS = {
    "theory": _write_theory,
    "architecture": _write_architecture,
    "concepts": _write_concepts,
    "use_cases": _write_use_cases,
    "labs": _write_labs,
    "simulations": _write_simulations,
    "projects": _write_projects,
    "troubleshooting": _write_troubleshooting,
    "interview": _write_interview,
    "scenario": _write_scenario,
    "assessment": _write_assessment,
    "certification": _write_certification,
    "enterprise": _write_enterprise,
    "best_practices": _write_best_practices,
    "security": _write_security,
    "performance": _write_performance,
    "monitoring": _write_monitoring,
    "incidents": _write_incidents,
    "rca": _write_rca,
    "notes": _write_notes,
}


# Topic fallback commands so EVERY module shows real syntax/commands even when a
# topic profile has no curated `commands` map. Keyed by a lowercase substring of
# the course topic. (lang, {section_key: command}).
_FALLBACK_CMDS: dict[str, tuple[str, dict[str, str]]] = {
    "linux": ("bash", {
        "labs": "id; whoami\nsystemctl status sshd\njournalctl -xe | tail -20",
        "troubleshooting": "journalctl -p err -b\ndmesg -T | tail\nss -tulpn",
        "monitoring": "top -b -n1 | head\nfree -h\ndf -h",
        "security": "sudo -l\ngetent passwd\nss -tulpn",
    }),
    "rhel": ("bash", {
        "labs": "subscription-manager status\ndnf repolist\nsystemctl status firewalld",
        "troubleshooting": "ausearch -m avc -ts recent\njournalctl -xe\ndnf history",
        "monitoring": "systemctl --failed\nchronyc tracking",
        "security": "getenforce\nfirewall-cmd --list-all\nsemanage boolean -l | head",
    }),
    "docker": ("bash", {
        "labs": "docker ps -a\ndocker compose up -d\ndocker logs <container>",
        "troubleshooting": "docker inspect <container> | jq '.[0].State'\ndocker logs --tail 50 <container>\ndocker stats --no-stream",
        "monitoring": "docker stats --no-stream\ndocker system df",
        "security": "docker scout cves <image>\ndocker inspect <container> | jq '.[0].HostConfig.Privileged'",
    }),
    "kubernetes": ("bash", {
        "labs": "kubectl get pods -A\nkubectl describe pod <pod>\nkubectl apply -f manifest.yaml",
        "troubleshooting": "kubectl get events --sort-by=.lastTimestamp\nkubectl logs <pod> --previous\nkubectl describe pod <pod>",
        "monitoring": "kubectl top pods\nkubectl get hpa",
        "security": "kubectl auth can-i --list\nkubectl get netpol",
    }),
    "terraform": ("hcl", {
        "labs": "terraform init\nterraform plan -out=tfplan\nterraform apply tfplan",
        "troubleshooting": "terraform plan -refresh-only\nterraform state list\nterraform validate",
        "monitoring": "terraform state list\nterraform show",
        "security": "terraform plan | grep -i 'sensitive\\|secret'",
    }),
    "ansible": ("yaml", {
        "labs": "ansible -m ping all\nansible-playbook site.yml --check --diff\nansible-playbook site.yml",
        "troubleshooting": "ansible-playbook site.yml -vvv\nansible -m setup <host>",
        "monitoring": "ansible all -m command -a 'uptime'",
        "security": "ansible-vault view secrets.yml",
    }),
    "python": ("python", {
        "labs": "python -m venv .venv && source .venv/bin/activate\npip install -r requirements.txt\npython -m pytest -q",
        "troubleshooting": "python -X faulthandler app.py\npython -m pdb app.py",
        "monitoring": "python -m cProfile -s cumtime app.py | head",
        "security": "pip-audit\nbandit -r .",
    }),
    "git": ("bash", {
        "labs": "git status\ngit checkout -b feature/x\ngit add -p && git commit -m 'msg'",
        "troubleshooting": "git log --oneline --graph --decorate\ngit reflog\ngit bisect start",
        "monitoring": "git log --stat -5",
        "security": "git secret list 2>/dev/null; git log -p | grep -i password | head",
    }),
    "sql": ("sql", {
        "labs": "SELECT version();\nEXPLAIN ANALYZE SELECT * FROM orders WHERE id = 1;",
        "troubleshooting": "SELECT * FROM pg_stat_activity WHERE state <> 'idle';",
        "monitoring": "SELECT * FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 5;",
        "security": "SELECT grantee, privilege_type FROM information_schema.role_table_grants LIMIT 10;",
    }),
    "prometheus": ("promql", {
        "labs": "up\nrate(http_requests_total[5m])\nhistogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
        "troubleshooting": "count(up == 0) by (job)",
        "monitoring": "rate(node_cpu_seconds_total{mode=\"idle\"}[5m])",
    }),
    "grafana": ("bash", {
        "labs": "# Add a Prometheus datasource, then build a panel:\nsum(rate(http_requests_total[5m])) by (status)",
        "troubleshooting": "curl -s http://localhost:3000/api/health",
        "monitoring": "curl -s http://localhost:3000/api/datasources",
    }),
}


def _fallback_for(topic: str) -> tuple[str, dict[str, str]] | None:
    t = (topic or "").lower()
    for key, val in _FALLBACK_CMDS.items():
        if key in t:
            return val
    return None


def _build_code(section_key: str, topic: str, module: str, profile: dict) -> tuple[str, str, str]:
    cmds = profile.get("commands") or {}
    fb = _fallback_for(topic)
    fb_lang = fb[0] if fb else "bash"
    fb_map = fb[1] if fb else {}

    if section_key == "labs":
        if cmds:
            key = next(iter(cmds))
            code = cmds[key] if isinstance(cmds[key], str) else str(cmds[key])
            return f"# {module}\n{code}", "bash", f"{topic} hands-on — run in playground"
        if fb_map.get("labs"):
            return f"# {module}\n{fb_map['labs']}", fb_lang, f"{topic} hands-on — run in playground"
    if section_key == "concepts":
        if cmds:
            code = "\n".join(f"# {k}\n{v}" for k, v in list(cmds.items())[:3])
            return code, "bash", "Reference commands for this module"
        if fb_map.get("labs"):
            return f"# Reference commands\n{fb_map['labs']}", fb_lang, "Reference commands for this module"
    if section_key == "troubleshooting":
        diag = fb_map.get("troubleshooting") or (list(cmds.values())[0] if cmds else "echo 'check logs, metrics, and recent changes'")
        return f"# Diagnose: {module}\n{diag}", fb_lang if fb_map.get("troubleshooting") else "bash", "Diagnostic starter"
    if section_key == "monitoring":
        mon = fb_map.get("monitoring") or (list(cmds.values())[-1] if cmds else "")
        if mon:
            return mon, fb_lang if fb_map.get("monitoring") else "bash", "Health / metrics check"
    if section_key == "security" and fb_map.get("security"):
        return f"# Security checks: {module}\n{fb_map['security']}", fb_lang, "Security/hardening checks"
    return "", "text", ""


def build_rich_module_sections(
    course: dict, module_title: str, level: str
) -> list[tuple[str, str, str, str, str]]:
    topic = course["topic"]
    playground = course.get("playground_slug") or topic.lower()
    profile = get_profile(topic)
    sections: list[tuple[str, str, str, str, str]] = []
    for heading, key in SECTION_HEADINGS:
        writer = _WRITERS[key]
        if key == "labs":
            book = get_book_body(topic, module_title, key, level)
            base = writer(topic, module_title, level, profile, playground)
            body = _enrich(key, topic, module_title, level, f"{book}\n\n---\n\n{base}")
        elif key == "notes":
            body = writer(topic, module_title, level, profile)
        else:
            book = get_book_body(topic, module_title, key, level)
            base = writer(topic, module_title, level, profile)
            merged_base = f"{book}\n\n---\n\n{base}"
            body = _enrich(key, topic, module_title, level, merged_base)
        code, lang, caption = _build_code(key, topic, module_title, profile)
        sections.append((heading, body, code, lang, caption))
    return sections
