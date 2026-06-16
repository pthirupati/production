"""Parse resume PDF/text into structured profile hints."""

from __future__ import annotations

import re


def extract_text_from_upload(uploaded_file) -> str:
    """Best-effort text extraction from uploaded resume."""
    if not uploaded_file:
        return ""
    name = (getattr(uploaded_file, "name", "") or "").lower()
    raw = uploaded_file.read()
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    if name.endswith(".pdf"):
        try:
            import pypdf

            reader = pypdf.PdfReader(uploaded_file)
            parts = []
            for page in reader.pages[:12]:
                parts.append(page.extract_text() or "")
            return "\n".join(parts).strip()
        except Exception:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass
            return raw.decode("utf-8", errors="ignore")[:20000]

    if name.endswith((".doc", ".docx")):
        return raw.decode("utf-8", errors="ignore")[:20000]

    try:
        return raw.decode("utf-8", errors="ignore")[:20000]
    except Exception:
        return ""


_SKILL_PATTERNS = [
    r"\b(python|java|golang|go|rust|javascript|typescript|react|angular|vue)\b",
    r"\b(linux|rhel|ubuntu|centos|bash|shell)\b",
    r"\b(docker|kubernetes|k8s|helm|terraform|ansible|jenkins|ci/cd)\b",
    r"\b(aws|azure|gcp|cloud)\b",
    r"\b(mysql|postgres|mongodb|redis|kafka)\b",
    r"\b(nginx|apache|httpd|load balancer)\b",
    r"\b(prometheus|grafana|elk|splunk|datadog)\b",
    r"\b(networking|tcp/ip|dns|firewall|vpn)\b",
]


def parse_resume_text(text: str) -> dict:
    """Lightweight resume analysis without external LLM."""
    low = (text or "").lower()
    skills = []
    for pat in _SKILL_PATTERNS:
        skills.extend(re.findall(pat, low, flags=re.I))
    skills = sorted(set(s.lower() for s in skills))

    years = 0
    ym = re.search(r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", low)
    if ym:
        years = int(ym.group(1))
    else:
        ym2 = re.search(r"experience[:\s]+(\d+)", low)
        if ym2:
            years = int(ym2.group(1))

    companies = re.findall(
        r"(?:at|@)\s+([A-Z][A-Za-z0-9&.\- ]{2,40})(?:\s|,|\||\n)",
        text or "",
    )[:5]

    roles = re.findall(
        r"(devops|sre|software engineer|system admin|linux admin|cloud engineer|platform engineer)",
        low,
    )

    return {
        "skills_detected": skills[:30],
        "years_experience_hint": years,
        "companies_mentioned": companies[:5],
        "roles_mentioned": list(dict.fromkeys(roles))[:5],
        "word_count": len((text or "").split()),
        "has_resume": bool(text and len(text.strip()) > 50),
    }
