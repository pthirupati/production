"""P2.R5 — Callback memory → phrasing (free, rule-based).

Quote tech/domain phrases back so the candidate feels remembered.
Whitelist against known tools / expected keywords — avoid arbitrary nouns.
"""

from __future__ import annotations

import random
import re
from typing import Any


_TECH_HINTS = (
    "terraform", "kubernetes", "k8s", "ansible", "awx", "docker", "aws", "azure",
    "gcp", "nginx", "postgres", "mysql", "redis", "kafka", "prometheus", "grafana",
    "nvidia", "gpu", "h100", "h200", "dcgm", "maas", "lxd", "vyos", "pxe",
    "sla", "slo", "incident", "deploy", "rollback", "cache", "ttl", "latency",
    "throughput", "cidr", "vpc", "iam", "oidc", "tls", "dns", "bgp", "vlan",
)


def extract_callback_phrases(
    answer_text: str,
    *,
    expected_keywords: list[str] | None = None,
    tools_mentioned: list[str] | None = None,
    max_phrases: int = 3,
) -> list[str]:
    """Pull 1–3 salient tech phrases co-occurring with known domain tokens."""
    text = (answer_text or "").strip()
    if len(text) < 12:
        return []
    whitelist = {t.lower() for t in _TECH_HINTS}
    for k in expected_keywords or []:
        if k:
            whitelist.add(str(k).lower().split()[0])
    for t in tools_mentioned or []:
        if t:
            whitelist.add(str(t).lower().split()[0])

    found: list[str] = []
    lower = text.lower()
    for token in sorted(whitelist, key=len, reverse=True):
        if len(token) < 3:
            continue
        if re.search(rf"\b{re.escape(token)}\b", lower):
            # Grab a short window around the token for natural quoting.
            m = re.search(rf"(.{{0,24}}\b{re.escape(token)}\b.{{0,24}})", text, re.I)
            snippet = (m.group(1).strip() if m else token).strip(" ,.;:")
            if snippet and snippet.lower() not in {f.lower() for f in found}:
                found.append(snippet[:60])
            if len(found) >= max_phrases:
                break
    return found


def maybe_callback_opener(
    phrases: list[str],
    *,
    chance: float = 0.30,
    rng: random.Random | None = None,
) -> str | None:
    if not phrases:
        return None
    r = rng or random.Random()
    if r.random() > chance:
        return None
    phrase = r.choice(phrases)
    templates = (
        f"Going back to what you mentioned about {phrase} — does that same tradeoff apply here?",
        f"Earlier you talked through {phrase} — how would that play out in this case?",
        f"You brought up {phrase} before — walk me through how it connects here.",
    )
    return r.choice(templates)


def cross_round_callback(prior_summary: str, *, rng: random.Random | None = None) -> str | None:
    """Manager/deep-dive open referencing a prior round summary."""
    summary = (prior_summary or "").strip()
    if len(summary) < 40:
        return None
    r = rng or random.Random()
    # Prefer a tech-bearing slice of the summary.
    phrases = extract_callback_phrases(summary)
    hook = phrases[0] if phrases else summary[:80].rstrip() + ("…" if len(summary) > 80 else "")
    templates = (
        f"I saw from the earlier round you covered {hook} — walk me through how you communicated that to your team.",
        f"Coming out of the technical round, you mentioned {hook}. How did stakeholders react?",
    )
    return r.choice(templates)


def remember_phrases(
    conv_meta: dict[str, Any],
    phrases: list[str],
    *,
    position: str = "mid",
) -> dict[str, Any]:
    out = dict(conv_meta or {})
    bag = list(out.get("callback_phrases") or [])
    for p in phrases:
        entry = {"phrase": p, "position": position}
        if p and p not in {x.get("phrase") for x in bag if isinstance(x, dict)}:
            bag.append(entry)
    out["callback_phrases"] = bag[:24]
    return out


def phrases_from_meta(conv_meta: dict[str, Any] | None) -> list[str]:
    if not isinstance(conv_meta, dict):
        return []
    out = []
    for item in conv_meta.get("callback_phrases") or []:
        if isinstance(item, dict) and item.get("phrase"):
            out.append(str(item["phrase"]))
        elif isinstance(item, str):
            out.append(item)
    return out
