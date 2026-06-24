"""Parse and query admin-uploaded interview answer corpora."""

from __future__ import annotations

import re

from apps.interviews.models import InterviewAnswerCorpus


def parse_answer_text(raw: str) -> list[dict]:
    """Turn a plain-text upload into structured entries with keywords."""
    entries = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip common Q/A prefixes: "Q:", "A:", "1.", "-"
        cleaned = re.sub(r"^(?:Q|A|Question|Answer)\s*[:.)-]\s*", "", line, flags=re.I)
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
        cleaned = cleaned.strip(" -•")
        if len(cleaned) < 8:
            continue
        words = re.findall(r"[a-z0-9][a-z0-9+.#-]{2,}", cleaned.lower())
        # Drop ultra-common tokens
        stop = {"the", "and", "for", "with", "that", "this", "from", "have", "your", "you", "are", "was", "were"}
        keywords = [w for w in words if w not in stop][:12]
        entries.append({"line": cleaned, "keywords": keywords})
    return entries


def corpus_keywords_for_technology(technology_id: int | None) -> list[str]:
    """Merged keyword list from all active corpora for a technology."""
    if not technology_id:
        return []
    keywords: list[str] = []
    for corpus in InterviewAnswerCorpus.objects.filter(
        technology_id=technology_id, is_active=True
    ).only("entries"):
        for entry in corpus.entries or []:
            keywords.extend(entry.get("keywords") or [])
    # De-dupe preserving order
    seen = set()
    out = []
    for k in keywords:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out[:80]
