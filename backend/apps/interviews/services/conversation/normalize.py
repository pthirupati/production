"""Repair common speech-to-text errors before analysis."""

from __future__ import annotations

import re

# Domain dictionary: misheard phrase -> canonical term
_STT_REPAIRS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bkube\s+cuttle\b", re.I), "kubectl"),
    (re.compile(r"\bkubernetes\b", re.I), "kubernetes"),
    (re.compile(r"\bcooper\s+neties\b", re.I), "kubernetes"),
    (re.compile(r"\bcooperneties\b", re.I), "kubernetes"),
    (re.compile(r"\bk\s*8\s*s\b", re.I), "k8s"),
    (re.compile(r"\bno\s+js\b", re.I), "Node.js"),
    (re.compile(r"\bnode\s+jay\s+ess\b", re.I), "Node.js"),
    (re.compile(r"\bprometheeus\b", re.I), "Prometheus"),
    (re.compile(r"\bgrafanah\b", re.I), "Grafana"),
    (re.compile(r"\bterraform\b", re.I), "Terraform"),
    (re.compile(r"\bansible\b", re.I), "Ansible"),
    (re.compile(r"\bdocker\b", re.I), "Docker"),
    (re.compile(r"\bjenkins\b", re.I), "Jenkins"),
    (re.compile(r"\bpostgress\b", re.I), "PostgreSQL"),
    (re.compile(r"\bpostgres\b", re.I), "PostgreSQL"),
]


def normalize_transcript(text: str) -> str:
    """Apply domain STT repairs; preserve original casing where possible."""
    out = text or ""
    for pattern, replacement in _STT_REPAIRS:
        out = pattern.sub(replacement, out)
    return re.sub(r"\s+", " ", out).strip()
