"""
Auto-generate deep module packs for every course module in the catalog.

Supplements hand-authored deep_modules entries with rich theory, concepts,
labs, troubleshooting, and notes for all 750+ lessons.
"""

from __future__ import annotations

import re


def _sentences(topic: str, module: str, level: str, aspect: str) -> str:
    return (
        f"For **{module}** at **{level}** level in **{topic}**, {aspect} "
        f"Operators document assumptions, measure before/after, and tie every change to a rollback plan. "
        f"In enterprise {topic} fleets, this topic appears in design reviews, change tickets, and on-call runbooks."
    )


def generate_deep_pack(topic: str, module: str, level: str, course_title: str) -> dict[str, str]:
    """Rich override sections merged into every module unless hand-authored."""
    ml = module.lower()
    return {
        "theory": (
            f"## Theory — {module}\n\n"
            f"Welcome to module **{module}** in *{course_title}* ({level} track). "
            f"This chapter is part of a complete {topic} textbook — read it end-to-end before labs.\n\n"
            f"{_sentences(topic, module, level, 'theory explains the mental model and vocabulary.')}\n\n"
            f"**Why this module exists:** Production {topic} teams split knowledge into modules like this so "
            f"juniors can learn progressively and seniors can audit gaps. You should finish this chapter able "
            f"to teach {ml} to a colleague without opening notes.\n\n"
            f"**Read in order:** prior modules → this chapter → hands-on lab → notes section → checklist.\n\n"
            f"**Depth bar:** If you cannot whiteboard {ml} with data flows, failure modes, and observability "
            f"signals, re-read before advancing to the next module."
        ),
        "architecture": (
            f"## Architecture — {module}\n\n"
            f"Draw **control plane** (configuration, orchestration) vs **data plane** (traffic, payloads) "
            f"for {ml}. Label every dependency: DNS, TLS, identity, storage, and monitoring.\n\n"
            f"**Components:** list each daemon, API, or service involved in {module}. Missing one box in "
            f"your diagram hides a failure domain.\n\n"
            f"**Scaling:** identify stateful vs stateless parts — state complicates failover and backup.\n\n"
            f"{_sentences(topic, module, level, 'architecture reviews start from this diagram.')}"
        ),
        "concepts": (
            f"## Core concepts — {module}\n\n"
            f"Memorize definitions precisely. Interviewers and incident commanders punish vague language.\n\n"
            f"- **Scope:** what {ml} includes and explicitly excludes in {topic}.\n"
            f"- **Inputs/outputs:** data or control flows entering and leaving this component.\n"
            f"- **Failure modes:** top three ways {ml} breaks in production.\n"
            f"- **Dependencies:** upstream/downstream services that must be healthy first.\n"
            f"- **Observability:** metrics/logs/traces that prove {ml} is healthy.\n\n"
            f"{_sentences(topic, module, level, 'each concept must link to a observable signal.')}"
        ),
        "use_cases": (
            f"## Use cases — {module}\n\n"
            f"- **Greenfield:** design {ml} with observability and security from day one.\n"
            f"- **Migration:** move legacy workloads with rollback gates and data validation.\n"
            f"- **Incident recovery:** restore service while preserving forensic evidence.\n"
            f"- **Compliance:** prove encryption, access control, and retention for audits.\n"
            f"- **Cost optimization:** right-size using utilization metrics without breaching SLOs."
        ),
        "labs": (
            f"## Hands-on labs — {module}\n\n"
            f"**Objective:** prove you can operate {ml} in FixitLab {topic} playground or linked scenario.\n\n"
            f"1. Read lab constraints and success criteria.\n"
            f"2. Reproduce baseline; capture logs/metrics snapshot.\n"
            f"3. Execute the procedure step-by-step; one change at a time.\n"
            f"4. Validate with Check Solution or peer rubric.\n"
            f"5. Write runbook: symptom → root cause → fix → verification.\n\n"
            f"Repeat the lab twice: once following hints, once cold."
        ),
        "troubleshooting": (
            f"## Troubleshooting — {module}\n\n"
            f"**Symptom catalog for {ml}:** slow responses, auth errors, partial outages, data inconsistency.\n\n"
            f"**First 15 minutes:** confirm scope → check recent deploys → collect logs → check dependencies "
            f"(DNS, TLS, disk, quotas) → mitigate → communicate → verify SLO.\n\n"
            f"**Never** restart without capturing evidence — postmortems depend on it."
        ),
        "interview": (
            f"## Interview questions — {module}\n\n"
            f"- Explain {ml} in two minutes.\n"
            f"- Design {topic} architecture including {ml} for 1M users.\n"
            f"- What metrics alert you before users notice {ml} failure?\n"
            f"- Describe rollback after a bad {ml} change.\n"
            f"- Compare managed vs self-hosted options for {topic}."
        ),
        "monitoring": (
            f"## Monitoring — {module}\n\n"
            f"Define SLIs for {ml}: latency p95/p99, error rate, saturation (CPU, memory, queue depth).\n\n"
            f"Wire dashboards that answer **healthy?** and **if not, why?** Every alert links to a runbook "
            f"with first steps for {topic} on-call."
        ),
        "security": (
            f"## Security — {module}\n\n"
            f"Apply least privilege to {ml}. Encrypt data in transit and at rest. Rotate credentials. "
            f"Threat-model insider and external attack paths. Log access for audit."
        ),
        "enterprise": (
            f"## Enterprise — {module}\n\n"
            f"Fortune-500 {topic} patterns: CAB-approved changes, multi-region DR, quarterly restore drills, "
            f"automated compliance scans, and executive-visible incident comms for {ml} outages."
        ),
        "notes": (
            f"## Notes — {module}\n\n"
            f"**Quick reference:** bookmark official {topic} docs for {ml}.\n\n"
            f"**Exam tips:** map this module to certification objectives; practice timed labs.\n\n"
            f"**Warnings:** destructive ops need tickets; test in staging mirroring prod topology.\n\n"
            f"**Spaced repetition:** revisit this chapter in 48 hours and again before interviews."
        ),
    }


def populate_deep_sections(deep_sections: dict, course_definitions: list) -> int:
    """Fill deep_sections for all catalog modules. Returns count added."""
    from ..course_catalog import LEVEL_BY_MODULE

    added = 0
    for course in course_definitions:
        slug = course["course_slug"]
        topic = course["topic"]
        title = course["course_title"]
        for idx, module_title in enumerate(course["modules"], start=1):
            key = (slug, idx)
            if key in deep_sections:
                continue
            level = LEVEL_BY_MODULE[min(idx - 1, len(LEVEL_BY_MODULE) - 1)]
            deep_sections[key] = generate_deep_pack(topic, module_title, level, title)
            added += 1
    return added
