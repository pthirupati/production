"""FixitLab native interview AI — 100% free, no external APIs.

Provides:
- Rich contextual follow-ups based on answer quality and topic
- Keyword-based STAR framework scoring
- Domain-specific question banks (DevOps, SRE, Kubernetes, Linux, Cloud, etc.)
- Adaptive difficulty based on conversation history
"""

from __future__ import annotations

import random
import re


# ---------------------------------------------------------------------------
# Keyword banks for semantic scoring (free alternative to embeddings)
# ---------------------------------------------------------------------------

_STAR_SITUATION = [
    "when", "we had", "there was", "the team", "our system", "at my previous", "at my current",
    "during", "last year", "incident", "project", "we were", "our org", "the scenario",
    "i was working", "my team was", "we needed",
]
_STAR_TASK = [
    "i was responsible", "my role was", "i needed to", "i had to", "it was my job",
    "i was tasked", "my goal was", "the requirement", "we needed to", "i owned",
    "i led the", "i was the lead",
]
_STAR_ACTION = [
    "i did", "i wrote", "i deployed", "i configured", "i implemented", "i fixed",
    "i created", "i ran", "i set up", "i built", "i automated", "i migrated",
    "i used", "i applied", "i changed", "i added", "i modified", "i investigated",
    "i analyzed", "i collaborated", "i coordinated", "i reached out", "i escalated",
    "i documented", "kubectl", "terraform", "ansible", "helm", "systemctl",
    "grep", "awk", "sed", "bash", "python", "git", "docker", "aws", "gcp", "azure",
]
_STAR_RESULT = [
    "as a result", "the outcome", "we reduced", "we improved", "latency dropped",
    "error rate", "uptime went", "saved", "faster", "resolved", "fixed",
    "mitigated", "the team was", "users reported", "the system", "postmortem",
    "we shipped", "we went from", "we achieved", "the fix worked", "zero downtime",
    "successful", "recovered", "deployed", "launched", "cut costs",
]

_TECHNICAL_DEPTH = [
    "because", "the reason", "tradeoff", "alternative", "we considered",
    "instead of", "compared to", "bottleneck", "root cause", "underlying",
    "specifically", "technically", "internally", "the way it works",
    "under the hood", "the algorithm", "complexity", "race condition",
    "idempotent", "eventual consistency", "cap theorem", "backpressure",
    "circuit breaker", "retry logic", "exponential backoff", "sla", "rto", "rpo",
    "metrics", "dashboards", "alerting", "oncall", "runbook", "postmortem",
]

_CONCRETE_EVIDENCE = [
    "%", "second", "millisecond", "request", "query", "pod", "node",
    "gb", "mb", "tps", "rps", "99th percentile", "p99", "p95", "p50",
    "container", "replica", "namespace", "instance", "cluster", "endpoint",
    "region", "availability zone", "cidr", "cpu", "memory", "disk",
]


# ---------------------------------------------------------------------------
# Rich reaction banks — contextual, persona-aware
# ---------------------------------------------------------------------------

_REACTIONS = {
    "strong": [
        "Right — now let me stress-test that. What breaks first when traffic doubles?",
        "Good instinct. How do you know that approach worked — what metric confirmed it?",
        "I like the direction. Walk me through how you'd do that with zero downtime.",
        "Solid. What would you do differently if you were starting from scratch today?",
        "That's the right call. How do you communicate that decision to a non-technical stakeholder?",
        "Good. Now scale that — how does your approach hold at 100x the load?",
        "Exactly. What's the rollback plan if something goes sideways mid-deploy?",
        "Nice. How would you automate that so the next engineer doesn't face the same problem?",
        "That's solid thinking. What's the observability story — how do you know it's healthy?",
    ],
    "strong_streak": [
        "You're on a roll. Let me push harder — describe the nastiest edge case you've actually hit.",
        "Strong answers. I want to see you handle ambiguity — what if requirements changed mid-incident?",
        "Impressive depth. Walk me through a time this approach actually failed you.",
        "You clearly know this space. Tell me about the most complex system you've debugged recently.",
        "Excellent. Now challenge your own answer — what's the weakest assumption in what you just said?",
    ],
    "weak": [
        "I'd want a bit more depth there. Walk me through the exact commands or steps you'd run.",
        "Help me understand your mental model — what's the failure mode you're most worried about?",
        "Let's slow down. What would you check first, before touching anything?",
        "I'm not quite seeing the technical path. How would you confirm your hypothesis before acting?",
        "Can you be more specific? What tool, command, or metric would tell you you're on the right track?",
        "Let's unpack that. What does 'it was slow' actually mean — what signal did you see?",
        "I need more. Walk me through your checklist — what do you verify in what order?",
    ],
    "brief": [
        "Short answer — can you expand? I'd love a real example from your experience.",
        "Tell me more. What was the actual command or config change you made?",
        "Walk me through the specifics. What did your monitoring show before you acted?",
        "I need more detail. What was the impact, and how did you measure improvement?",
        "That's a start. Give me the full picture — what happened before, during, and after.",
    ],
    "skipped": [
        "No worries — let's move on.",
        "Okay, we can come back to that later. Next question:",
        "Got it, let's keep pace —",
    ],
    "missing_star_s": [
        "Tell me more about the context first. What was the situation — what system, what team size?",
        "Set the scene for me — what was the environment when this happened?",
        "I want to understand the setup. What was going wrong before you got involved?",
    ],
    "missing_star_a": [
        "I hear the problem — what did you specifically do to address it, step by step?",
        "What were your actual steps? Walk me through them sequentially.",
        "Tell me exactly what you did. Start with: 'First, I...'",
    ],
    "missing_star_r": [
        "What was the outcome? How did you know the fix actually worked?",
        "What happened after — did it hold, or did you need to iterate?",
        "How did you measure success? Give me a number if you can.",
    ],
}

_ROUND_NUDGES = {
    "hr": [
        "By the way, what does your ideal team culture look like?",
        "What would make you say yes to an offer in the next few weeks?",
        "How important is remote flexibility to you in your next role?",
        "What's driving your search right now — growth, compensation, tech stack?",
        "Where do you see yourself in two years if this role went well?",
    ],
    "manager": [
        "How would you prioritize that against three other P1 incidents happening simultaneously?",
        "When do you escalate versus handle it yourself — what's your threshold?",
        "How do you write the incident postmortem so it's actually useful?",
        "How do you keep a cross-functional team aligned during a prolonged outage?",
        "What does 'blameless postmortem' actually mean to you in practice?",
    ],
    "behavioral": [
        "Let me probe the result — what metric improved, and by how much?",
        "What did you learn from that experience that you carry forward today?",
        "If you could redo that situation, what would you do differently?",
    ],
    "devops_debug": [
        "What does your rollback plan look like before you make that change?",
        "Have you checked whether this might be a dependency or a platform issue?",
        "What did the runbook say to do — and did you follow it or deviate?",
    ],
    "sre_oncall": [
        "Have you updated the incident channel? Stakeholders need status every 15 minutes.",
        "What's your hypothesis about root cause — and how do you test it safely in prod?",
        "Is this worth a severity-1 page, or can it wait for business hours?",
    ],
}

_TOPIC_FOLLOWUPS = {
    "kubernetes": [
        "What happens to that pod during a node eviction event?",
        "How does your approach change if you can't use privileged containers?",
        "Walk me through debugging a CrashLoopBackOff with only kubectl.",
        "How do you handle secrets rotation in a running Kubernetes cluster?",
        "What's your strategy for managing Helm chart upgrades safely in production?",
    ],
    "docker": [
        "How do you keep image layers small in a CI/CD context?",
        "What's your strategy for handling long-running containers that leak memory?",
        "How do you debug a container that exits immediately after starting?",
        "How do you manage multi-stage builds for compiled languages?",
    ],
    "nginx": [
        "How do you handle a zero-downtime nginx config reload?",
        "Walk me through diagnosing a 502 that only happens under load.",
        "How would you limit request rate per client without losing legitimate traffic?",
        "How do you set up mutual TLS termination at the nginx reverse proxy layer?",
    ],
    "linux": [
        "How do you find which process is consuming the most file descriptors?",
        "A server's load average is 80 but CPU is only 15% — what's going on?",
        "Walk me through diagnosing a 'disk full' that's not showing full on df.",
        "How do you troubleshoot a process that's stuck in 'D' state?",
    ],
    "monitoring": [
        "How do you prevent alert fatigue in a noisy Prometheus setup?",
        "Walk me through setting up SLIs and SLOs for a payment service.",
        "When would you use a gauge vs counter vs histogram in Prometheus?",
        "How do you handle cardinality explosions in your metrics?",
    ],
    "aws": [
        "How do you handle an Auto Scaling group stuck with unhealthy instances?",
        "Walk me through your strategy for cross-region failover with RTO under 5 minutes.",
        "How do you audit IAM permissions in an account with 300+ roles?",
        "What's your approach to managing AWS costs without slowing development?",
    ],
    "terraform": [
        "How do you handle a Terraform state file that's locked or corrupted?",
        "What's your strategy for managing Terraform across 50 microservices?",
        "How do you test Terraform changes safely before applying to production?",
        "How do you handle drift between Terraform state and actual infrastructure?",
    ],
    "ci_cd": [
        "How do you handle a CI pipeline that's grown to over 30 minutes?",
        "What's your strategy for rolling back a bad release automatically?",
        "How do you enforce compliance checks in CI without blocking developers?",
        "How do you manage secrets in a CI/CD pipeline securely?",
    ],
    "python": [
        "How do you debug a Python service that's leaking memory over hours?",
        "Walk me through your approach to profiling a slow Django endpoint.",
        "How do you handle thread safety in a Python microservice?",
        "What's your strategy for managing Python dependencies in production?",
    ],
    "ansible": [
        "How do you handle an Ansible playbook on 200 hosts — some idempotent, some not?",
        "What's your strategy for secret management in Ansible without Vault?",
        "How do you test Ansible roles in CI without a real inventory?",
        "How do you handle partial failures in a large Ansible run?",
    ],
    "security": [
        "How do you detect lateral movement after a credential leak?",
        "Walk me through your incident response for a suspected container escape.",
        "How do you enforce least-privilege in a microservices environment?",
        "How do you handle a CVE that affects a critical production dependency?",
    ],
    "database": [
        "How do you perform a zero-downtime schema migration on a 500GB table?",
        "What's your strategy for debugging slow queries in production?",
        "Walk me through your backup and restore verification process.",
        "How do you handle replication lag in a high-write PostgreSQL setup?",
    ],
}

_GENERIC_FOLLOWUPS = [
    "Let me push on that — what's the failure scenario you haven't mentioned yet?",
    "How would you prove to a skeptical senior engineer that this is the right call?",
    "Walk me through your runbook for this. What's step-by-step?",
    "What's the monitoring or alerting you'd set up to catch this earlier next time?",
    "If you had to teach this to a junior engineer, how would you explain it in two minutes?",
    "What assumptions are you making here that could be wrong?",
    "How does this hold up if you're managing this across three different cloud providers?",
    "What's the compliance or security angle you'd want to verify before going to production?",
    "What would you do if that approach failed at step three?",
]


# ---------------------------------------------------------------------------
# Human-touch banks (P2.3): varied acknowledgements + casual asides + openers
# that reference the candidate's OWN words. All free/templated — no LLM.
# ---------------------------------------------------------------------------

# Short acknowledgements rotated so we never repeat "good answer". {phrase}
# (when present) is filled with a fragment quoted from the candidate's answer.
_ACK_WITH_PHRASE = [
    "You touched on “{phrase}” — let's dig into that.",
    "The bit about “{phrase}” stood out to me.",
    "You mentioned “{phrase}”, and I want to pull on that thread.",
    "Okay, so “{phrase}” — that's the part I'm curious about.",
    "I noticed you said “{phrase}”.",
    "Picking up on “{phrase}” for a second.",
    "“{phrase}” — that's interesting.",
    "Let me zoom in on “{phrase}”.",
]

# Acknowledgements when we couldn't pull a clean phrase. Deliberately varied so
# a long round never repeats the same opener twice in a row. These short human
# fillers/back-channels (FIX 2 reply style) are what make the bot read as a live
# person reacting in the moment rather than a quiz reading the next item.
_ACK_GENERIC = [
    "Got it.",
    "Makes sense.",
    "Okay, I follow.",
    "Right.",
    "Fair enough.",
    "I hear you.",
    "Understood.",
    "Noted.",
    "That tracks.",
    "Mm-hm.",
    "Yeah, okay.",
    "Right, right.",
    "Gotcha.",
    "Okay, with you.",
    "Sure, that makes sense.",
    "Mm, okay.",
]

# Tiny conversational connectors occasionally stitched between the acknowledgement
# and the follow-up so the turn flows like speech ("Right — so, what breaks…")
# instead of two clipped sentences. Kept varied; deduped per round like the rest.
_CONNECTORS = [
    "so,",
    "now,",
    "okay so,",
    "alright, so",
    "here's what I'm curious about —",
    "let me ask you this —",
]

# Light, human asides occasionally prepended/appended (kept professional, low
# frequency) so the bot doesn't feel like a survey form.
_CASUAL_ASIDES = [
    "No rush —",
    "Just thinking out loud here —",
    "Between us,",
    "Honestly,",
    "Quick one —",
    "Real-world question —",
    "Curveball —",
]

# Words too generic to be worth quoting back ("you mentioned 'the'…" is silly).
_PHRASE_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "so", "if", "of", "to", "in", "on",
    "for", "with", "as", "at", "by", "is", "was", "were", "be", "been", "are",
    "it", "that", "this", "these", "those", "i", "we", "you", "they", "he",
    "she", "my", "our", "your", "their", "me", "us", "them", "do", "did",
    "does", "have", "has", "had", "will", "would", "can", "could", "should",
    "just", "really", "very", "kind", "sort", "like", "well", "okay", "um",
    "uh", "yeah", "yes", "no", "not", "then", "than", "when", "what", "how",
    "why", "where", "which", "who", "about", "into", "from", "out", "up",
    "down", "over", "after", "before", "because", "thing", "things", "stuff",
    "lot", "bit", "way", "get", "got", "make", "made", "use", "used", "using",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _score_star_coverage(answer: str) -> dict[str, bool]:
    low = answer.lower()
    return {
        "situation": any(k in low for k in _STAR_SITUATION),
        "task": any(k in low for k in _STAR_TASK),
        "action": any(k in low for k in _STAR_ACTION),
        "result": any(k in low for k in _STAR_RESULT),
    }


def _detect_topic(text: str) -> str | None:
    low = text.lower()
    topic_keywords = {
        "kubernetes": ["kubernetes", "k8s", "kubectl", "pod", "deployment", "helm", "namespace", "ingress"],
        "docker": ["docker", "container", "dockerfile", "image", "registry", "compose"],
        "nginx": ["nginx", "reverse proxy", "upstream", "ssl termination", "load balance"],
        "linux": ["linux", "systemd", "kernel", "cgroup", "process", "inode", "socket", "file descriptor"],
        "monitoring": ["prometheus", "grafana", "alertmanager", "metrics", "slo", "sli", "error rate"],
        "aws": ["aws", "ec2", "s3", "rds", "cloudwatch", "iam", "vpc", "lambda", "eks"],
        "terraform": ["terraform", "tfstate", "provider", "resource", "plan apply", "module"],
        "ci_cd": ["ci/cd", "pipeline", "github actions", "jenkins", "gitlab", "argocd", "deployment"],
        "python": ["python", "django", "flask", "fastapi", "asyncio", "pip", "celery"],
        "ansible": ["ansible", "playbook", "inventory", "roles", "handler", "task"],
        "security": ["security", "vulnerability", "cve", "secret", "credential", "iam", "rbac", "privilege"],
        "database": ["database", "postgres", "mysql", "mongodb", "redis", "migration", "schema"],
    }
    scores = {t: sum(1 for k in kws if k in low) for t, kws in topic_keywords.items()}
    best = max(scores, key=lambda t: scores[t])
    return best if scores[best] >= 2 else None


def _assess_quality(answer: str, question: str = "") -> str:
    if not answer or len(answer.strip()) < 20:
        return "skipped"
    word_count = len(answer.split())
    if word_count < 30:
        return "brief"
    low = answer.lower()
    depth_hits = sum(1 for k in _TECHNICAL_DEPTH if k in low)
    concrete_hits = sum(1 for k in _CONCRETE_EVIDENCE if k in low)
    action_hits = sum(1 for k in _STAR_ACTION if k in low)
    result_hits = sum(1 for k in _STAR_RESULT if k in low)
    score = (
        min(depth_hits, 4) * 2
        + min(concrete_hits, 4) * 2
        + min(action_hits, 5) * 1
        + min(result_hits, 3) * 1.5
        + min(word_count / 80, 2) * 1
    )
    if score >= 8:
        return "strong"
    if score >= 4:
        return "adequate"
    return "weak"


# ---------------------------------------------------------------------------
# Human-touch helpers (P2.3)
# ---------------------------------------------------------------------------

# Technical multi-word phrases worth quoting verbatim if the candidate used them.
_NOTABLE_BIGRAMS = (
    "cache ttl", "circuit breaker", "blast radius", "rolling deploy",
    "blue green", "feature flag", "root cause", "race condition",
    "connection pool", "rate limit", "load balancer", "message queue",
    "read replica", "write path", "hot path", "cold start", "back pressure",
    "graceful shutdown", "health check", "liveness probe", "readiness probe",
    "node eviction", "memory leak", "disk io", "exponential backoff",
    "eventual consistency", "two phase commit", "schema migration",
    "secret rotation", "least privilege", "incident response", "error budget",
    "tail latency", "p99 latency", "garbage collection", "thread pool",
)


def _extract_quote_phrase(answer: str) -> str | None:
    """Pull a short, meaningful phrase from the candidate's OWN answer so the
    follow-up can reference it (e.g. 'You touched on "the cache TTL"…').

    Strategy, all deterministic & free:
      1. Prefer a known technical bigram the candidate actually used.
      2. Otherwise take the first run of >=2 consecutive 'content' words
         (non-stopword, alphabetic) — that reads like a natural noun phrase.
      3. Otherwise fall back to the single longest content word.
    Returns None if nothing worth quoting (so the caller uses a generic ack).
    """
    if not answer:
        return None
    low = answer.lower()

    for bigram in _NOTABLE_BIGRAMS:
        if bigram in low:
            return bigram

    # Tokenize into alphabetic words, preserving order.
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]+", answer)
    if not words:
        return None

    def is_content(w: str) -> bool:
        return len(w) >= 3 and w.lower() not in _PHRASE_STOPWORDS

    # First run of 2–4 consecutive content words.
    run: list[str] = []
    best_run: list[str] = []
    for w in words:
        if is_content(w):
            run.append(w)
            if len(run) > len(best_run):
                best_run = run[:4]
        else:
            run = []
    if len(best_run) >= 2:
        return " ".join(best_run).lower()

    # Single longest content word as a last resort.
    content_words = [w for w in words if is_content(w)]
    if content_words:
        longest = max(content_words, key=len)
        if len(longest) >= 5:
            return longest.lower()
    return None


def _prior_interviewer_lines(conversation_tail: list[dict]) -> set[str]:
    """Normalized set of interviewer lines already spoken this session (from the
    tail the engine passes) so we don't repeat the exact same question/opener."""
    seen: set[str] = set()
    for m in conversation_tail or []:
        if m.get("role") == "interviewer":
            seen.add(_normalize(m.get("content", "")))
    return seen


def _last_interviewer_line(conversation_tail: list[dict]) -> str:
    """Normalized text of the most recent interviewer line, so we can guarantee
    we never say the exact same thing twice in a row. ``conversation_tail`` is
    ordered oldest→newest, so we scan from the end."""
    for m in reversed(conversation_tail or []):
        if m.get("role") == "interviewer":
            return _normalize(m.get("content", ""))
    return ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _lower_first(text: str) -> str:
    """Lowercase the first letter so a body reads smoothly after a connector/aside
    that ends in a comma or dash. Leaves the standalone pronoun "I" and obvious
    acronyms (two+ leading capitals, e.g. "SLA", "TLS") capitalised."""
    if not text:
        return text
    first_word = text.split(" ", 1)[0]
    if first_word == "I" or first_word.startswith("I "):
        return text
    # ALL-CAPS / acronym start (e.g. "SLA", "CPU") — don't lowercase.
    if len(first_word) >= 2 and first_word[:2].isupper():
        return text
    if text[:1].isupper():
        return text[:1].lower() + text[1:]
    return text


def _pick_unused(options: list[str], used: set[str], rng: random.Random) -> str:
    """Choose an option whose normalized form isn't already in `used`. Falls back
    to any option if all have been used (very long rounds). Records the choice."""
    if not options:
        return ""
    shuffled = options[:]
    rng.shuffle(shuffled)
    for opt in shuffled:
        if _normalize(opt) not in used:
            used.add(_normalize(opt))
            return opt
    choice = shuffled[0]
    used.add(_normalize(choice))
    return choice


def _compose_ack(phrase: str | None, used: set[str], rng: random.Random) -> str:
    """Build a varied acknowledgement, quoting the candidate's phrase when we
    have one. Never reuses an acknowledgement already used this round."""
    if phrase:
        templates = [t.format(phrase=phrase) for t in _ACK_WITH_PHRASE]
        ack = _pick_unused(templates, used, rng)
        if ack:
            return ack
    return _pick_unused(_ACK_GENERIC, used, rng)


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def generate_interviewer_reply(
    *,
    persona_name: str,
    round_type: str,
    question_text: str,
    candidate_answer: str,
    score_hint: dict,
    profile_snapshot: dict,
    conversation_tail: list[dict],
    strong_streak: int = 0,
) -> str:
    """
    Generate a natural, context-aware interviewer follow-up.
    100% free — no external LLM or paid API required.

    P2.3 — sounds more human, less robotic:
      * The opener references the candidate's OWN words (a phrase pulled from
        their last answer) instead of a canned "good answer".
      * Acknowledgements + follow-ups are de-duplicated against what's already
        been said this session (we read the interviewer lines the engine passes
        in ``conversation_tail``), so long rounds don't repeat themselves.
      * An occasional light/casual aside is mixed in.
    """
    quality = score_hint.get("quality") or _assess_quality(candidate_answer, question_text)
    company = profile_snapshot.get("current_company") or "your current org"
    role = profile_snapshot.get("target_role") or profile_snapshot.get("experience_level", "mid")

    # Lines already spoken this round → don't repeat openers / questions.
    used = _prior_interviewer_lines(conversation_tail)
    last_line = _last_interviewer_line(conversation_tail)
    # Seed RNG off what's been said so picks vary turn-to-turn but stay free.
    rng = random.Random()
    phrase = _extract_quote_phrase(candidate_answer) if quality not in ("skipped",) else None

    def finish(reply: str) -> str:
        """Guarantee we never (a) return an empty line, or (b) say the exact
        same thing as the immediately-previous interviewer turn."""
        text = (reply or "").strip()
        if not _normalize(text):
            text = _pick_unused(_GENERIC_FOLLOWUPS, used, rng) or "Got it — let's keep going."
        if last_line and _normalize(text) == last_line:
            # Collided with the previous line — append a distinct, unused tail.
            extra = _pick_unused(_GENERIC_FOLLOWUPS, used, rng)
            text = f"{text} {extra}".strip() if extra else f"{text} Tell me more."
        return text

    # STAR gap detection for behavioral/HR rounds
    if round_type in ("behavioral", "hr") and candidate_answer and len(candidate_answer) > 40:
        star = _score_star_coverage(candidate_answer)
        missing = [k for k, v in star.items() if not v]
        if quality != "skipped" and len(missing) >= 2:
            if "situation" in missing:
                return finish(_pick_unused(_REACTIONS["missing_star_s"], used, rng))
            if "action" in missing:
                return finish(_pick_unused(_REACTIONS["missing_star_a"], used, rng))
            if "result" in missing:
                return finish(_pick_unused(_REACTIONS["missing_star_r"], used, rng))

    # Skipped: short, varied, no quoting.
    if quality == "skipped":
        return finish(_pick_unused(_REACTIONS["skipped"], used, rng))

    # Human acknowledgement that quotes the candidate when possible.
    ack = _compose_ack(phrase, used, rng)

    # The "push" reaction (deduped) carries the substance of the follow-up.
    if quality == "strong":
        reaction = _pick_unused(
            _REACTIONS["strong_streak"] if strong_streak >= 4 else _REACTIONS["strong"],
            used, rng,
        )
    elif quality == "weak":
        reaction = _pick_unused(_REACTIONS["weak"], used, rng)
    elif quality == "brief":
        reaction = _pick_unused(_REACTIONS["brief"], used, rng)
    else:
        reaction = _pick_unused(_REACTIONS["strong"], used, rng)

    # Topic-specific follow-up (40% chance) — replaces the generic reaction tail.
    combined = f"{question_text} {candidate_answer}"
    topic = _detect_topic(combined)
    tail_followup = None
    if topic and rng.random() < 0.40:
        tail_followup = _pick_unused(
            _TOPIC_FOLLOWUPS.get(topic, _GENERIC_FOLLOWUPS), used, rng
        )
    else:
        nudges = _ROUND_NUDGES.get(round_type, [])
        if nudges and rng.random() < 0.35:
            tail_followup = _pick_unused(nudges, used, rng)

    # Candidate asked a question back — answer it, then redirect (still human).
    if candidate_answer and candidate_answer.rstrip().endswith("?"):
        flip = (
            "Good question — it depends on blast radius and rollback strategy. "
            "But let me flip it back: how have you actually made that call before?"
        )
        return finish(f"{ack} {flip}" if phrase else flip)

    # Resume/experience reference.
    if candidate_answer and re.search(r"\b(resume|cv|previous|my experience|i worked at)\b", candidate_answer, re.I):
        body = (
            f"Your {role} background sounds relevant — "
            f"how would you apply that on a new team where everything is set up differently?"
        )
        return finish(f"{ack} {body}")

    # Company-personalized follow-up (15% chance).
    if rng.random() < 0.15 and company != "your current org":
        return finish(f"{ack} At a company like {company}, what constraints would change your approach?")

    body = tail_followup or reaction
    # Occasional casual aside (~18%), but never on a weak answer (stay focused).
    parts = [ack]
    aside = ""
    if quality != "weak" and rng.random() < 0.18:
        aside = _pick_unused(_CASUAL_ASIDES, used, rng)
    if aside:
        # Asides end in a comma/dash, so lowercase the body's first letter for
        # smoother prose ("Honestly, what breaks first…" not "Honestly, What…").
        parts.append(aside)
        body = _lower_first(body)
    elif quality != "weak" and rng.random() < 0.30:
        # No aside — sometimes stitch a light spoken connector so the reply flows
        # into the follow-up like a real conversation ("Right — so, what breaks…")
        # rather than two clipped sentences. Skip on weak answers (stay direct).
        connector = _pick_unused(_CONNECTORS, used, rng)
        if connector:
            parts.append(connector)
            body = _lower_first(body)
    parts.append(body)
    reply = " ".join(p for p in parts if p).strip()
    return finish(reply)


# ---------------------------------------------------------------------------
# Score breakdown (used by scoring engine)
# ---------------------------------------------------------------------------

def compute_answer_scores(
    *,
    candidate_answer: str,
    question_text: str,
    round_type: str,
    expected_keywords: list[str] | None = None,
) -> dict:
    """Return structured score breakdown — fully free, no external API."""
    quality = _assess_quality(candidate_answer, question_text)
    star = _score_star_coverage(candidate_answer)
    topic = _detect_topic(f"{question_text} {candidate_answer}")
    word_count = len(candidate_answer.split()) if candidate_answer else 0
    low = (candidate_answer or "").lower()

    depth_score = min(100, sum(1 for k in _TECHNICAL_DEPTH if k in low) * 12)
    concrete_score = min(100, sum(1 for k in _CONCRETE_EVIDENCE if k in low) * 15)
    star_score = round(sum(star.values()) / 4 * 100)
    length_score = min(100, word_count * 1.5) if word_count < 70 else min(100, word_count * 0.8)

    expected_hit_rate = 0.0
    if expected_keywords:
        # Keywords come from JSONField data that may have been seeded or edited
        # with non-string entries (None, ints). Coerce defensively so a single
        # bad keyword can never crash live answer scoring (was a raw 500).
        clean_keywords = [str(k).lower() for k in expected_keywords if k not in (None, "")]
        if clean_keywords:
            hits = sum(1 for k in clean_keywords if k in low)
            expected_hit_rate = hits / len(clean_keywords)
        else:
            expected_keywords = None

    if round_type in ("behavioral", "hr"):
        composite = depth_score * 0.20 + concrete_score * 0.15 + star_score * 0.45 + length_score * 0.20
    elif round_type in ("system_design", "live_coding"):
        composite = depth_score * 0.45 + concrete_score * 0.35 + star_score * 0.05 + length_score * 0.15
    else:
        composite = depth_score * 0.35 + concrete_score * 0.30 + star_score * 0.15 + length_score * 0.20

    if expected_keywords:
        composite = composite * 0.7 + expected_hit_rate * 100 * 0.3

    return {
        "quality": quality,
        "composite_score": round(min(100, max(0, composite))),
        "depth_score": depth_score,
        "concrete_score": concrete_score,
        "star_score": star_score,
        "star_coverage": star,
        "word_count": word_count,
        "topic_detected": topic,
        "keyword_hit_rate": round(expected_hit_rate, 2),
        "feedback": _generate_feedback(quality, star, topic, round_type),
    }


def _generate_feedback(quality: str, star: dict, topic: str | None, round_type: str) -> str:
    if quality == "skipped":
        return "No answer provided."
    if quality == "strong":
        return "Strong, detailed response with technical depth and concrete evidence."
    if quality == "brief":
        return "Answer was too brief — add specific examples, commands, or metrics."
    if quality == "weak":
        missing = [k.capitalize() for k, v in star.items() if not v]
        base = "Answer lacked technical specificity. "
        if missing and round_type in ("behavioral", "hr"):
            base += f"Missing STAR components: {', '.join(missing)}. "
        if topic:
            base += f"Expand on the {topic} aspect with concrete steps or data."
        return base.strip()
    missing = [k.capitalize() for k, v in star.items() if not v]
    if missing and round_type in ("behavioral", "hr"):
        return f"Good answer. Consider adding: {', '.join(missing)} for a complete STAR response."
    return "Adequate response — add specific data points or metrics to strengthen it."
