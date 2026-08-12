"""FixitLab native interview AI — 100% free, no external APIs.

Provides:
- Rich contextual follow-ups based on answer quality and topic
- Keyword-based STAR framework scoring
- Domain-specific question banks (DevOps, SRE, Kubernetes, Linux, Cloud, etc.)
- Adaptive difficulty based on conversation history
"""

from __future__ import annotations

import hashlib
import random
import re


def _seeded_rng(*parts) -> random.Random:
    """Deterministic RNG from conversation / answer material (audit §Y1g).

    Comment sites previously claimed seeding then called ``random.Random()``
    with no seed — nondeterministic and untestable across processes.
    """
    blob = "|".join("" if p is None else str(p) for p in parts)
    digest = hashlib.blake2b(blob.encode("utf-8", errors="replace"), digest_size=8).digest()
    return random.Random(int.from_bytes(digest, "big"))


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
    # Kept for import compatibility; scoring uses analysis.score_technical_depth.
    "root cause", "tradeoff", "bottleneck", "under the hood", "race condition",
    "idempotent", "eventual consistency", "backpressure", "circuit breaker",
    "exponential backoff", "runbook", "postmortem",
]

_CONCRETE_EVIDENCE = [
    # Kept for import compatibility; scoring uses analysis.score_concrete_evidence.
    # Ambiguous English ("second", "request") intentionally removed.
    "millisecond", "pod", "node", "gb", "mb", "tps", "rps", "99th percentile",
    "p99", "p95", "p50", "container", "replica", "namespace", "instance",
    "cluster", "endpoint", "region", "availability zone", "cidr", "cpu", "memory", "disk",
]

# Filler words stripped before keyword scoring so "um, I'd restart nginx" still hits.
_FILLER_RE = re.compile(
    r"\b(um+|uh+|er+|erm+|like|you know|sort of|kind of|basically|literally|actually)\b",
    re.I,
)

# Synonym expansion for expected-keyword matching — accepts spoken variants.
_KEYWORD_SYNONYMS: dict[str, list[str]] = {
    "restart": ["reboot", "reload", "bounce", "start again", "bring back up"],
    "nginx": ["web server", "reverse proxy"],
    "systemctl": ["systemd", "service nginx", "service command"],
    "kubectl": ["k8s cli", "kube control"],
    "pod": ["pods", "container group"],
    "deployment": ["deploy", "rolling update"],
    "rollback": ["roll back", "revert", "undo deploy"],
    "scale": ["scaling", "autoscale", "hpa", "replicas"],
    "monitor": ["monitoring", "observability", "watch", "metrics"],
    "log": ["logs", "logging", "journalctl", "log line"],
    "cache": ["caching", "redis", "memcached", "ttl"],
    "iam": ["identity", "permissions", "access control"],
    "role": ["roles", "assume role", "sts"],
    "policy": ["policies", "permission document"],
    "association": ["group membership", "attached to group", "through group"],
    "terraform": ["tf", "infrastructure as code", "iac"],
    "ansible": ["playbook", "configuration management"],
    "docker": ["container", "containerized"],
    "ingress": ["load balancer", "routing rule"],
    "secret": ["secrets", "credentials", "vault"],
    "backup": ["restore", "snapshot", "dr"],
    "latency": ["slow", "p99", "response time"],
    "debug": ["troubleshoot", "investigate", "diagnose"],
    "curl": ["http check", "health check"],
    "prometheus": ["metrics", "monitoring", "time series"],
    "grafana": ["dashboard", "visualization", "monitoring"],
    "helm": ["chart", "package manager", "k8s deploy"],
    "postgres": ["postgresql", "sql database", "rdbms"],
    "redis": ["cache", "in-memory", "key value"],
    "kafka": ["event stream", "message broker", "queue"],
    "lambda": ["serverless", "function", "faas"],
    "vpc": ["network", "subnet", "private cloud"],
    "certificate": ["tls", "ssl", "https"],
    "firewall": ["security group", "iptables", "acl"],
    "oncall": ["on-call", "on call", "pager", "incident response"],
    "slo": ["service level objective", "error budget", "sla"],
    "runbook": ["playbook", "procedure", "operational doc"],
    "ci/cd": ["pipeline", "continuous integration", "continuous delivery", "github actions"],
    "kubernetes": ["k8s", "kube", "cluster orchestration"],
    "observability": ["metrics logs traces", "otel", "apm", "monitoring stack"],
    "root cause": ["rca", "five whys", "underlying cause", "why it happened"],
}


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
        "Help me connect the dots — what would you check or run first in practice?",
        "Walk me through your mental model — what's the first signal you'd look at?",
        "I want to hear the practical path — what tool or command would you reach for?",
        "Paint me the scene — what would you verify before making a change?",
        "Talk me through it like we're on a bridge call — what's step one?",
    ],
    "brief": [
        "That's a start — can you add a concrete example from something you've actually done?",
        "Give me one more layer — what command, config, or metric backs that up?",
        "Walk me through the specifics — what did you see in monitoring or logs?",
        "I'd love a bit more color — what happened before, during, and after?",
        "Expand on that — even one real incident example would help.",
    ],
    "skipped": [
        "No worries — let's keep moving.",
        "That's fine, we'll circle back if we have time.",
        "All good — let's keep pace.",
        "No problem at all — moving on.",
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

# Verdict-aware reaction bank (WS2) — keyed on the correctness signal the scorer
# emits ("correct" | "partial" | "off_base" | "unknown"). These lead the human
# reaction so the bot actually reacts to *whether they were right*, not just how
# long they talked. Combined with the phrase-quoting acknowledgement, the reply
# reads like a real interviewer who heard and judged the answer.
_VERDICT_REACTIONS = {
    "correct": [
        "Yeah, that's right.",
        "Exactly — that's the answer I was looking for.",
        "Spot on.",
        "That's correct, and you framed it well.",
        "Right, that lines up with how I'd approach it too.",
        "Good — you nailed the key idea there.",
    ],
    "partial": [
        "You're on the right track — there's just one piece I'd want to tighten.",
        "Good start — you've got part of it, and I want to hear the rest of your thinking.",
        "Yeah, that's directionally right. Let me see if we can nail the missing bit.",
        "Okay, you've got the shape of it — let's sharpen one detail.",
    ],
    "off_base": [
        "I think we might be talking past each other — let me reframe what I'm after.",
        "That's a fair angle, though not quite the thread I was pulling on.",
        "Okay — different direction than I had in mind, but let's steer back together.",
        "Hmm, I may not have been clear — let me put the question another way.",
    ],
    "unknown": [
        "Okay.",
        "Alright.",
        "Let's see.",
        "Got it.",
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


# Clarify/probe lines (WS2) — used when the prior answer was brief/weak so the
# SAME question is re-asked rather than advancing. {phrase} is filled from the
# candidate's own words when available. Always asks them to go concrete.
_CLARIFY_PROBES = [
    "Thanks — I follow the gist on {phrase}. Can you walk me through the actual steps you'd take?",
    "I hear you on {phrase}. What would that look like in practice — tools, commands, or order of operations?",
    "Good start on {phrase}. Help me picture the hands-on part — what would you do first?",
    "That makes sense at a high level. For {phrase}, what's the concrete sequence you'd follow?",
]
_CLARIFY_PROBES_NO_PHRASE = [
    "Thanks — I follow the gist. Can you walk me through the actual steps you'd take?",
    "I hear you. What would that look like in practice — tools, commands, or order of operations?",
    "Good start. Help me picture the hands-on part — what would you do first?",
    "That makes sense at a high level. What's the concrete sequence you'd follow on a real system?",
]
_CLARIFY_PARTIAL = [
    "You're on the right track with {phrase} — can you flesh out the steps a bit more?",
    "Good direction on {phrase}. What's the hands-on sequence — tools and order?",
    "I follow {phrase} — one more layer of detail would nail it for me.",
]
_CLARIFY_PARTIAL_NO_PHRASE = [
    "You're on the right track — can you flesh out the steps a bit more?",
    "Good direction. What's the hands-on sequence — tools and order?",
    "I follow the gist — one more layer of detail would nail it for me.",
]

# Natural bridges spoken before the next question lands (engine appends to reply).
_TRANSITION_CORRECT = [
    "Alright — let's keep the momentum going.",
    "Good — shifting gears a little.",
    "Nice. Next one for you.",
    "Okay, moving on.",
]
_TRANSITION_PARTIAL = [
    "Thanks — let's try a related angle.",
    "Got the gist — here's a follow-up.",
    "Fair enough — let's keep going.",
]
_TRANSITION_SKIPPED = [
    "No worries — next one:",
    "All good — let's keep pace.",
]
_TRANSITION_DEFAULT = [
    "Let's move on.",
    "Next question.",
]

# ---------------------------------------------------------------------------
# Candidate-asks-a-question responder banks (WS5). All free/local — when the
# candidate interrupts to ask something instead of answering, we ANSWER it and
# re-ask the SAME question without scoring/advancing.
# ---------------------------------------------------------------------------

# Patterns that mark the candidate's text as a question/meta-request rather than
# an answer (used alongside input_type=="question" and a trailing "?").
_META_QUESTION_PATTERNS = (
    "can you repeat", "could you repeat", "say that again", "repeat the question",
    "what do you mean", "what does that mean", "not sure what you mean",
    "can you clarify", "could you clarify", "please clarify", "clarify",
    "can you explain", "could you explain", "what is", "what's a", "what are",
    "i don't understand", "didn't understand", "didn't catch", "did not catch",
    "rephrase", "come again", "what was the question",
)

# Short, on-topic definitions pulled from our existing topic vocabulary so a
# "what is X?" can be answered without any external API.
_TERM_DEFINITIONS = {
    "kubernetes": "Kubernetes is a container orchestrator — it schedules containers across nodes and keeps the declared desired state.",
    "pod": "A pod is the smallest deployable unit in Kubernetes — one or more containers sharing network and storage.",
    "deployment": "A Deployment manages a replicated, self-healing set of pods and handles rolling updates for you.",
    "statefulset": "A StatefulSet manages stateful pods with stable identities and stable storage — used for databases and the like.",
    "readiness probe": "A readiness probe tells Kubernetes when a pod is ready to receive traffic; failing it pulls the pod out of the load balancer.",
    "liveness probe": "A liveness probe tells Kubernetes when to restart a container that's wedged but still running.",
    "docker": "Docker packages an app and its dependencies into an image you can run as an isolated container anywhere.",
    "container": "A container is an isolated process running from an image, sharing the host kernel but with its own filesystem and namespaces.",
    "image": "An image is the immutable, layered template a container is started from.",
    "nginx": "nginx is a high-performance web server and reverse proxy that routes traffic to upstream services.",
    "reverse proxy": "A reverse proxy sits in front of your services and forwards client requests to them, often adding TLS, caching, or rate limiting.",
    "load balancer": "A load balancer spreads incoming requests across multiple backends so no single one is overwhelmed.",
    "slo": "An SLO is a target for a reliability metric (an SLI) over a window — e.g. 99.9% of requests under 300ms.",
    "sli": "An SLI is the actual measured signal of service health, like success rate or latency.",
    "sla": "An SLA is the contractual promise to a customer, usually backed by penalties if you miss it.",
    "idempotent": "Idempotent means running the operation again produces the same result — safe to retry without side effects.",
    "circuit breaker": "A circuit breaker stops calling a failing dependency for a while so you don't pile on load while it recovers.",
    "blast radius": "Blast radius is how much breaks when one thing fails — you design to keep it small.",
    "terraform": "Terraform declares infrastructure as code and reconciles real resources to that declared state via a state file.",
    "ansible": "Ansible is agentless configuration management — it pushes idempotent tasks to hosts over SSH from a playbook.",
    "ci_cd": "CI builds and tests every change; CD takes a passing build and releases it, ideally automatically.",
    "monitoring": "Monitoring collects metrics, logs, and traces so you can see — and alert on — how a system is behaving.",
    "security": "Security here means least-privilege access, secret hygiene, and limiting what a single compromise can reach.",
    "database": "A database stores and serves structured data; in ops we care about replication, backups, and migration safety.",
    "networking": "Networking covers how packets get from client to service — DNS, routing, firewalls, and the OSI layers in between.",
    "python": "Python is a high-level language widely used for automation, services, and tooling in ops and SRE work.",
    "iam": "IAM (Identity and Access Management) controls who can do what in a cloud account — users, groups, roles, and the policies attached to them.",
    "access through association": (
        "Access through association means you get permissions because you're linked to something else, "
        "not because a policy is glued directly to you. Real AWS example: developers are in the IAM group "
        "'Deployers' with AmazonEC2ReadOnlyAccess attached to the group. Alice has no EC2 policy on her user, "
        "but she can describe instances because group membership associates her with that access. Same idea for "
        "a role's trust policy letting an EC2 instance assume the role, or an SCP associated to an OU in "
        "Organizations."
    ),
    "role": "An IAM role is an identity with permissions that a trusted principal (user, service, or account) can assume temporarily via STS — common for EC2, Lambda, and cross-account access.",
    "policy": "An IAM policy is a JSON document listing allowed or denied actions on resources; it attaches to users, groups, roles, or is used inline.",
    "assume role": "To assume a role is to exchange your current credentials for short-lived STS credentials scoped to that role's permissions — e.g. an EC2 instance assuming a role to reach S3.",
    "sts": "AWS STS (Security Token Service) issues temporary credentials when you assume a role or federate in — typically 15 minutes to 12 hours.",
    "scp": "A Service Control Policy (SCP) is an Organizations guardrail: it limits what accounts in an OU can do even if their IAM policies allow it.",
}

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

def _normalize_answer_for_scoring(text: str) -> str:
    """Strip fillers and collapse whitespace for fairer keyword matching."""
    t = _FILLER_RE.sub(" ", (text or "").strip())
    return re.sub(r"\s+", " ", t).strip().lower()


def _expand_for_keyword_match(text: str) -> str:
    """Expand answer text with synonym tokens so spoken variants still score."""
    low = _normalize_answer_for_scoring(text)
    extras: list[str] = []
    for base, syns in _KEYWORD_SYNONYMS.items():
        if base in low:
            extras.extend(syns)
        else:
            for s in syns:
                if s in low:
                    extras.append(base)
                    break
    if not extras:
        return low
    return f"{low} {' '.join(extras)}"


def _keyword_matches(expanded_text: str, keyword: str) -> bool:
    """True when keyword or a known synonym/base form appears in expanded text."""
    kw = (keyword or "").strip().lower()
    if not kw:
        return False
    if kw in expanded_text:
        return True
    for syn in _KEYWORD_SYNONYMS.get(kw, []):
        if syn in expanded_text:
            return True
    for base, syn_list in _KEYWORD_SYNONYMS.items():
        if kw in syn_list and base in expanded_text:
            return True
    return False


def _count_keyword_hits(answer_text: str, keywords: list[str]) -> tuple[int, float]:
    expanded = _expand_for_keyword_match(answer_text)
    if not keywords:
        return 0, 0.0
    hits = sum(1 for k in keywords if _keyword_matches(expanded, k))
    return hits, hits / len(keywords)


def _effective_reply_quality(quality: str, correctness: str) -> str:
    """Map scorer quality + correctness to the reaction tone — concise-but-correct
    answers shouldn't get a harsh 'go deeper' push."""
    if quality == "skipped":
        return quality
    if correctness == "correct" and quality in ("brief", "weak"):
        return "adequate"
    if correctness == "partial":
        if quality == "weak":
            return "brief"
        if quality == "brief":
            return "adequate"
    return quality


def _detect_topic(text: str) -> str | None:
    low = text.lower()
    topic_keywords = {
        "kubernetes": ["kubernetes", "k8s", "kubectl", "pod", "deployment", "helm", "namespace", "ingress"],
        "docker": ["docker", "container", "dockerfile", "image", "registry", "compose"],
        "nginx": ["nginx", "reverse proxy", "upstream", "ssl termination", "load balance"],
        "linux": ["linux", "systemd", "kernel", "cgroup", "process", "inode", "socket", "file descriptor"],
        "monitoring": ["prometheus", "grafana", "alertmanager", "metrics", "slo", "sli", "error rate"],
        "aws": ["aws", "ec2", "s3", "rds", "cloudwatch", "iam", "vpc", "lambda", "eks", "sts", "scp"],
        "terraform": ["terraform", "tfstate", "provider", "resource", "plan apply", "module"],
        "ci_cd": ["ci/cd", "pipeline", "github actions", "jenkins", "gitlab", "argocd", "deployment"],
        "python": ["python", "django", "flask", "fastapi", "asyncio", "pip", "celery"],
        "ansible": ["ansible", "playbook", "inventory", "roles", "handler", "task"],
        "security": ["security", "vulnerability", "cve", "secret", "credential", "iam", "rbac", "privilege"],
        "database": ["database", "postgres", "mysql", "mongodb", "redis", "migration", "schema"],
    }
    scores = {t: sum(1 for k in kws if k in low) for t, kws in topic_keywords.items()}
    best = max(scores, key=lambda t: scores[t])
    if scores[best] >= 2:
        return best
    # A single strong signal (e.g. "kubectl get pods") is enough for short answers.
    if scores[best] == 1:
        return best
    return None


_FILLER_ONLY = frozenset({
    "ok", "okay", "yes", "no", "sure", "idk", "maybe", "nope", "yeah", "yep", "nah",
    "not sure", "don't know", "dont know", "pass", "skip", "hmm", "um", "uh",
})

_COMMAND_TOKENS = re.compile(
    r"\b(kubectl|systemctl|terraform|ansible|docker|aws|az|gcloud|grep|curl|ssh|"
    r"journalctl|helm|nginx|iptables|ip\s|ping|dig|nslookup|chmod|chown|sed|awk)\b",
    re.I,
)


def _refine_quality(
    quality: str,
    *,
    correctness: str | None = None,
    keyword_hit_rate: float = 0.0,
    topic: str | None = None,
    word_count: int = 0,
    has_keywords: bool = False,
) -> str:
    """Adjust length-only quality using correctness + on-topic signals.

    A concise but correct answer should read as adequate, not brief/weak."""
    if quality == "skipped":
        return quality
    if correctness == "correct":
        if quality in ("brief", "weak"):
            return "adequate"
    if correctness == "partial":
        if quality == "weak" and (keyword_hit_rate >= 0.3 or topic):
            return "brief"
        if quality == "brief" and keyword_hit_rate >= 0.35:
            return "adequate"
    if topic and word_count >= 6 and quality == "weak":
        if keyword_hit_rate >= 0.2 or not has_keywords:
            return "adequate"
    if keyword_hit_rate >= 0.55 and quality in ("brief", "weak"):
        return "adequate"
    return quality


def _score_star_coverage(answer: str) -> dict[str, bool]:
    low = answer.lower()
    return {
        "situation": any(k in low for k in _STAR_SITUATION),
        "task": any(k in low for k in _STAR_TASK),
        "action": any(k in low for k in _STAR_ACTION),
        "result": any(k in low for k in _STAR_RESULT),
    }


def _assess_quality(answer: str, question: str = "") -> str:
    text = (answer or "").strip()
    if not text:
        return "skipped"
    word_count = len(text.split())
    low = text.lower()
    if word_count <= 2 and low.rstrip(".!?") in _FILLER_ONLY:
        return "skipped"

    from apps.interviews.services.conversation.analysis import (
        score_concrete_evidence,
        score_technical_depth,
    )

    depth_hits = score_technical_depth(text) // 20
    concrete_hits = score_concrete_evidence(text) // 20
    action_hits = sum(1 for k in _STAR_ACTION if k in low)
    result_hits = sum(1 for k in _STAR_RESULT if k in low)
    command_like = bool(_COMMAND_TOKENS.search(low))
    score = (
        min(depth_hits, 4) * 2
        + min(concrete_hits, 4) * 2
        + min(action_hits, 5) * 1
        + min(result_hits, 3) * 1.5
        + (2 if command_like else 0)
        + min(word_count / 60, 2) * 1
    )
    if score >= 8:
        return "strong"
    if score >= 4:
        return "adequate"
    # Concise but substantive (commands, tooling, clear action) — don't punish brevity.
    if score >= 2 and word_count >= 5:
        return "adequate"
    if word_count >= 20 and score >= 1:
        return "adequate"
    if word_count < 10 and score < 2:
        return "brief"
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


# Phrases that read like interviewer prompts — never quote them back from answers.
_PHRASE_BLOCKLIST = (
    "access through association", "go deeper", "real example", "concrete example",
    "walk me through", "step by step", "tell me again", "say that again",
)


def _is_blocked_phrase(phrase: str) -> bool:
    if not phrase:
        return True
    low = phrase.lower()
    if any(b in low for b in _PHRASE_BLOCKLIST):
        return True
    return low in _TERM_DEFINITIONS


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
        if bigram in low and not _is_blocked_phrase(bigram):
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
        phrase = " ".join(best_run).lower()
        if not _is_blocked_phrase(phrase):
            return phrase

    # Single longest content word as a last resort.
    content_words = [w for w in words if is_content(w)]
    if content_words:
        longest = max(content_words, key=len)
        if len(longest) >= 5 and not _is_blocked_phrase(longest.lower()):
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
    # Correctness verdict (WS2) — drives a verdict-aware reaction so the reply
    # reacts to *whether they were right*, not just how long they spoke.
    correctness = score_hint.get("correctness") or "unknown"
    reply_quality = _effective_reply_quality(quality, correctness)
    company = profile_snapshot.get("current_company") or "your current org"
    role = profile_snapshot.get("target_role") or profile_snapshot.get("experience_level", "mid")

    # Lines already spoken this round → don't repeat openers / questions.
    used = _prior_interviewer_lines(conversation_tail)
    last_line = _last_interviewer_line(conversation_tail)
    # Seed RNG off what's been said so picks vary turn-to-turn but stay free.
    rng = _seeded_rng(
        candidate_answer,
        "".join((m.get("content") or "")[:40] for m in (conversation_tail or [])),
        quality,
        correctness,
    )
    phrase = _extract_quote_phrase(candidate_answer) if quality not in ("skipped",) else None

    def verdict_reaction() -> str:
        """A short reaction keyed on the correctness verdict, deduped per round.
        Empty string for 'unknown' so we don't editorialize when we can't judge."""
        if correctness in ("correct", "partial", "off_base"):
            return _pick_unused(_VERDICT_REACTIONS.get(correctness, []), used, rng)
        return ""

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
        # Optional self-hosted LLM phrasing (audit Y1f) — rules still decided content.
        try:
            from .voice_stack import llm_generate_reply

            polished = llm_generate_reply(
                system=(
                    "You are a concise technical interviewer reacting to a candidate. "
                    "Rewrite the line below in natural spoken English. Keep meaning, "
                    "under 45 words, no preamble."
                ),
                user=text,
                max_tokens=100,
            )
            if polished and len(polished.strip()) > 12:
                text = polished.strip()
        except Exception:  # noqa: BLE001
            pass
        return text

    # Human acknowledgement that quotes the candidate when possible — built up
    # front so EVERY non-skipped reply LEADS by referencing what they actually
    # said (WS2). The verdict reaction (correct/partial/off_base) rides in front
    # of it so the bot reacts to whether they were right, then quotes them.
    verdict = verdict_reaction() if quality != "skipped" else ""
    if quality != "skipped" and score_hint.get("barge_in"):
        verdict = _pick_unused(
            [
                "No problem at all — jump in anytime.",
                "Sure — go ahead, I'm listening.",
                "All good — take the floor.",
                "That's fine — I was just wrapping up.",
            ],
            used,
            rng,
        ) or "No problem — go ahead."
    memory = score_hint.get("memory") if isinstance(score_hint.get("memory"), dict) else {}

    if quality != "skipped" and memory:
        from apps.interviews.services.conversation_intelligence import (
            detect_contradiction,
            generate_contradiction_probe,
            generate_off_topic_redirect,
            tone_adaptive_opener,
        )
        prior = detect_contradiction(memory, candidate_answer)
        if prior and rng.random() < 0.6:
            probe = generate_contradiction_probe(prior, used, rng)
            return finish(probe)

    if quality != "skipped":
        from apps.interviews.services.conversation_intelligence import (
            generate_off_topic_redirect,
            tone_adaptive_opener,
        )
        tone_line = tone_adaptive_opener(memory, used, rng)
        if tone_line and rng.random() < 0.55:
            verdict = f"{verdict} {tone_line}".strip() if verdict else tone_line
        redirect = generate_off_topic_redirect(
            answer_text=candidate_answer,
            question_text=question_text,
            question_topic=score_hint.get("question_topic") or _detect_topic(question_text),
            used=used,
            rng=rng,
        )
        if redirect and score_hint.get("correctness") in ("off_base", "unknown") and rng.random() < 0.5:
            return finish(f"{verdict} {redirect}".strip() if verdict else redirect)

        if phrase:
            ack = _compose_ack(phrase, used, rng)
        else:
            from apps.interviews.services.persona_style import persona_ack
            ack = persona_ack(round_type, used, rng)
    else:
        ack = ""

    q_category = score_hint.get("question_category") or ""
    if q_category == "system_design" and quality != "skipped":
        from apps.interviews.services.system_design import system_design_reply_probe
        sd_probe = system_design_reply_probe(
            candidate_answer=candidate_answer,
            question_text=question_text,
            conversation_tail=conversation_tail,
        )
        if sd_probe:
            ack = sd_probe

    q_kind = score_hint.get("question_kind") or ""
    if q_kind in ("live_coding", "live_coding_followup") and quality != "skipped":
        from apps.interviews.services.live_coding import live_coding_reply_probe

        lc_probe = live_coding_reply_probe(
            candidate_answer=candidate_answer,
            expected_signals=score_hint.get("expected_signals") or [],
            phase=score_hint.get("live_coding_phase") or "",
        )
        if lc_probe:
            ack = lc_probe

    def lead(*rest: str) -> str:
        """Compose: <verdict reaction> <phrase-quoting ack> <follow-up...>."""
        pieces = [p for p in (verdict, ack, *rest) if p and p.strip()]
        return finish(" ".join(pieces))

    # STAR gap detection for behavioral/HR rounds
    if round_type in ("behavioral", "hr") and candidate_answer and len(candidate_answer) > 40:
        star = _score_star_coverage(candidate_answer)
        missing = [k for k, v in star.items() if not v]
        if quality != "skipped" and len(missing) >= 2:
            if "situation" in missing:
                return lead(_pick_unused(_REACTIONS["missing_star_s"], used, rng))
            if "action" in missing:
                return lead(_pick_unused(_REACTIONS["missing_star_a"], used, rng))
            if "result" in missing:
                return lead(_pick_unused(_REACTIONS["missing_star_r"], used, rng))

    # Skipped: short, varied, no quoting.
    if quality == "skipped":
        return finish(_pick_unused(_REACTIONS["skipped"], used, rng))

    # The "push" reaction (deduped) carries the substance of the follow-up.
    if reply_quality == "strong":
        reaction = _pick_unused(
            _REACTIONS["strong_streak"] if strong_streak >= 4 else _REACTIONS["strong"],
            used, rng,
        )
    elif reply_quality == "weak":
        reaction = _pick_unused(_REACTIONS["weak"], used, rng)
    elif reply_quality == "brief":
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
    # NOTE: the engine (WS5) now intercepts genuine candidate questions BEFORE
    # this function and routes them to generate_clarification_reply, so this is a
    # backstop for the rare case the engine still calls us with a trailing "?".
    if candidate_answer and candidate_answer.rstrip().endswith("?"):
        flip = (
            "Good question — it depends on blast radius and rollback strategy. "
            "But let me flip it back: how have you actually made that call before?"
        )
        return lead(flip)

    # Resume/experience reference.
    if candidate_answer and re.search(r"\b(resume|cv|previous|my experience|i worked at)\b", candidate_answer, re.I):
        body = (
            f"Your {role} background sounds relevant — "
            f"how would you apply that on a new team where everything is set up differently?"
        )
        return lead(body)

    # Company-personalized follow-up (15% chance).
    if rng.random() < 0.15 and company != "your current org":
        return lead(f"At a company like {company}, what constraints would change your approach?")

    body = tail_followup or reaction
    # Occasional casual aside (~18%), but never on a weak answer (stay focused).
    parts = [p for p in (verdict, ack) if p]
    aside = ""
    from apps.interviews.services.persona_style import persona_asides, persona_connectors, apply_vocabulary
    if reply_quality != "weak" and rng.random() < 0.18:
        pool = persona_asides(round_type) + _CASUAL_ASIDES
        aside = _pick_unused(pool, used, rng)
    if aside:
        # Asides end in a comma/dash, so lowercase the body's first letter for
        # smoother prose ("Honestly, what breaks first…" not "Honestly, What…").
        parts.append(aside)
        body = _lower_first(body)
    elif reply_quality != "weak" and rng.random() < 0.30:
        # No aside — sometimes stitch a light spoken connector so the reply flows
        # into the follow-up like a real conversation ("Right — so, what breaks…")
        # rather than two clipped sentences. Skip on weak answers (stay direct).
        pool = persona_connectors(round_type) + _CONNECTORS
        connector = _pick_unused(pool, used, rng)
        if connector:
            parts.append(connector)
            body = _lower_first(body)
    parts.append(body)
    reply = " ".join(p for p in parts if p).strip()
    return apply_vocabulary(finish(reply), round_type, rng)


# ---------------------------------------------------------------------------
# Warm round closing — spoken before the report (free/local).
# ---------------------------------------------------------------------------

_CLOSING_PASSED = [
    "That wraps our time — really solid conversation. You'll see detailed feedback in your report.",
    "Good round — thanks for walking through all of that. Check your scorecard for specifics.",
    "Nice work getting through that — I'll put my notes together in your report now.",
]

_CLOSING_Mixed = [
    "That wraps our time — thanks for sticking with it. Your report has concrete areas to sharpen.",
    "Appreciate you working through those — feedback is in your scorecard with specific next steps.",
]

_CLOSING_HR = [
    "Thanks for sharing your story today — really helpful context. Your report is ready when you are.",
    "Great chatting — I enjoyed learning about your background. You'll find feedback in your report.",
]


def generate_round_closing(
    *,
    round_type: str,
    passed: bool,
    memory: dict | None = None,
    persona_name: str = "",
) -> str:
    mem = memory if isinstance(memory, dict) else {}
    tone = mem.get("tone") or "neutral"
    name = (persona_name or "your interviewer").split()[0]
    pool = _CLOSING_PASSED if passed else _CLOSING_Mixed
    if round_type == "hr":
        pool = _CLOSING_HR
    rng = _seeded_rng(round_type, passed, tone, name, mem.get("strong_streak", 0))
    line = rng.choice(pool)
    if tone == "nervous" and passed:
        line = f"{line} You settled in well as we went — trust that pace."
    if int(mem.get("strong_streak", 0)) >= 3:
        line = f"{line} Strong finish from you."
    return f"{line} — {name}."


# ---------------------------------------------------------------------------
# WS2 — clarify/probe re-ask (interviewer asks the SAME question again because
# the prior answer was too thin to advance on). Leads with a phrase-quoting
# acknowledgement so it feels like the bot heard them, then asks for concrete
# detail. The engine re-asks the original question text after this reply.
# ---------------------------------------------------------------------------

def generate_clarify_probe(
    *,
    candidate_answer: str,
    question_text: str = "",
    conversation_tail: list[dict] | None = None,
    correctness: str | None = None,
) -> str:
    """Return a clarify/probe line that re-opens the SAME question (WS2).

    Free/local. Quotes the candidate's own phrase when one exists ('walk me
    through "the cache TTL" concretely') so the re-prompt reads like a real
    interviewer pressing for specifics rather than a canned retry."""
    used = _prior_interviewer_lines(conversation_tail or [])
    rng = _seeded_rng(
        candidate_answer,
        question_text,
        "".join((m.get("content") or "")[:40] for m in (conversation_tail or [])),
        correctness,
    )
    phrase = _extract_quote_phrase(candidate_answer)
    partial = correctness == "partial"
    if phrase:
        bank = _CLARIFY_PARTIAL if partial else _CLARIFY_PROBES
        templates = [t.format(phrase=f"“{phrase}”") for t in bank]
        line = _pick_unused(templates, used, rng)
        if line:
            q = (question_text or "").strip()
            if q:
                return f"{line} So again: {q}"
            return line
    no_phrase = _CLARIFY_PARTIAL_NO_PHRASE if partial else _CLARIFY_PROBES_NO_PHRASE
    line = _pick_unused(no_phrase, used, rng)
    line = line or "Thanks — can you walk me through that concretely, step by step?"
    q = (question_text or "").strip()
    if q:
        return f"{line} So again: {q}"
    return line


def generate_transition_bridge(
    *,
    round_type: str,
    quality: str,
    correctness: str,
    conversation_tail: list[dict] | None = None,
) -> str:
    """Short spoken bridge before the next question — keeps pacing human."""
    used = _prior_interviewer_lines(conversation_tail or [])
    rng = _seeded_rng(
        round_type,
        quality,
        correctness,
        "".join((m.get("content") or "")[:40] for m in (conversation_tail or [])),
    )
    if quality == "skipped":
        pool = _TRANSITION_SKIPPED
    elif correctness == "correct":
        pool = _TRANSITION_CORRECT
    elif correctness == "partial":
        pool = _TRANSITION_PARTIAL
    else:
        pool = _TRANSITION_DEFAULT
    return _pick_unused(pool, used, rng) or pool[0]


# ---------------------------------------------------------------------------
# Force-advance (user skip / next question) + unclear-audio re-asks. Human,
# empathetic — never frames skip or bad audio as a "wrong answer".
# ---------------------------------------------------------------------------

_FORCE_ADVANCE_REPLIES = [
    "No problem — let's move on to the next one.",
    "Sure thing — keeping us on pace. Here's the next question.",
    "All good — we'll come back to that if we have time. Next one:",
    "Absolutely — let's jump to the next question.",
]

_FORCE_ADVANCE_PARTIAL = [
    "Got the gist — let's keep moving and come back if we have time.",
    "Thanks — I'll note that and we'll keep pace with the next question.",
]

_FORCE_ADVANCE_END = [
    "No problem — that wraps the questions for this round. Nice work getting through it.",
    "All good — we're out of questions for this round. Let's wrap up.",
]

_UNCLEAR_AUDIO_REPLIES = [
    "Sorry — I didn't catch that clearly. Could be the line or a bit of background noise on my end.",
    "I'm having trouble hearing you on that one — that's on the audio, not your answer. Could you try once more?",
    "I lost you there for a second — no worries at all. Mind saying that again?",
    "The audio cut out a little — that's on my end, not your answer. Mind running through it once more?",
]


def generate_force_advance_reply(
    *,
    had_partial_answer: bool = False,
    has_next_question: bool = True,
    conversation_tail: list[dict] | None = None,
) -> str:
    used = _prior_interviewer_lines(conversation_tail or [])
    rng = _seeded_rng(
        had_partial_answer,
        has_next_question,
        "".join((m.get("content") or "")[:40] for m in (conversation_tail or [])),
    )
    if not has_next_question:
        return _pick_unused(_FORCE_ADVANCE_END, used, rng) or _FORCE_ADVANCE_END[0]
    if had_partial_answer:
        return _pick_unused(_FORCE_ADVANCE_PARTIAL, used, rng) or _FORCE_ADVANCE_PARTIAL[0]
    return _pick_unused(_FORCE_ADVANCE_REPLIES, used, rng) or _FORCE_ADVANCE_REPLIES[0]


def generate_unclear_audio_reply(
    *,
    question_text: str = "",
    partial_transcript: str = "",
    conversation_tail: list[dict] | None = None,
) -> str:
    used = _prior_interviewer_lines(conversation_tail or [])
    rng = _seeded_rng(
        question_text,
        partial_transcript,
        "".join((m.get("content") or "")[:40] for m in (conversation_tail or [])),
    )
    q = (question_text or "").strip()
    words = len((partial_transcript or "").split())
    if words >= 3:
        lead = (
            "I caught part of what you said but not the full answer — "
            "could be the connection. No judgment on the content, I just need to hear you clearly."
        )
    else:
        lead = _pick_unused(_UNCLEAR_AUDIO_REPLIES, used, rng) or _UNCLEAR_AUDIO_REPLIES[0]
    if q:
        return f"{lead} Same question: {q}"
    return lead


# ---------------------------------------------------------------------------
# WS5 — candidate asks a question / interrupts. We ANSWER it (repeat / rephrase /
# define a term / scope) and re-ask the SAME question WITHOUT scoring/advancing.
# Intent-keyed responder, all free/local — replaces the single canned flip-back.
# ---------------------------------------------------------------------------

def detect_question_intent(text: str) -> str | None:
    """Classify a candidate interruption into an intent the responder can answer.

    Returns ``repeat`` | ``definition`` | ``clarify`` | ``scope`` | ``generic``
    when the text reads as a question/meta-request, else ``None`` (it's a real
    answer). Free/local — keyword + punctuation heuristics only."""
    if not text:
        return None
    low = text.strip().lower()
    ends_q = low.endswith("?")

    # Repeat / didn't-catch.
    if any(p in low for p in ("repeat", "say that again", "come again", "what was the question", "didn't catch", "did not catch")):
        return "repeat"
    # Definition ("what is X", "what's a Y", "what do you mean by Z", "go deeper on X").
    if (
        low.startswith(("what is", "what's", "what are", "whats "))
        or "what do you mean" in low
        or "what does that mean" in low
        or "go deeper" in low
        or "real example" in low
        or "concrete example" in low
        or "with an example" in low
    ):
        return "definition"
    # Scope ("how much detail", "do you want code", "high level or deep").
    if any(p in low for p in ("how much detail", "how deep", "high level", "do you want", "should i", "are you looking for", "in detail")):
        return "scope"
    # Generic clarify request.
    if any(p in low for p in ("clarify", "rephrase", "explain", "don't understand", "do not understand", "not sure what you mean")):
        return "clarify"
    # Otherwise it's only a "question" if it actually ends with '?'.
    if ends_q:
        return "generic"
    return None


def _define_term(text: str, question_text: str) -> str | None:
    """Find a short on-topic definition for a term the candidate asked about."""
    low = f"{text} {question_text}".lower()
    # Direct term hits first (longest key wins so 'readiness probe' beats 'probe').
    for term in sorted(_TERM_DEFINITIONS, key=len, reverse=True):
        if term in low:
            return _TERM_DEFINITIONS[term]
    # Fall back to the detected topic's definition.
    topic = _detect_topic(low)
    if topic and topic in _TERM_DEFINITIONS:
        return _TERM_DEFINITIONS[topic]
    return None


def generate_clarification_reply(
    *,
    candidate_question: str,
    question_text: str,
    intent: str | None = None,
    conversation_tail: list[dict] | None = None,
) -> str:
    """Answer a candidate's interruption, then re-ask the SAME question (WS5).

    The engine calls this INSTEAD of scoring when the candidate is asking rather
    than answering (input_type=='question', trailing '?', or a meta pattern). It
    never advances and never scores. 100% free/local — repeats/rephrases the
    current question or returns a short on-topic definition from the topic banks.
    """
    intent = intent or detect_question_intent(candidate_question) or "generic"
    q = (question_text or "").strip()
    reask = q if q else "Let me restate it."

    if intent == "repeat":
        return f"Sure — here it is again: {reask}"
    if intent == "definition":
        definition = _define_term(candidate_question, question_text)
        if definition:
            return f"Good question — here's a concrete take. {definition} With that in mind: {reask}"
        return f"Good question — think of it in plain terms and answer from your own experience. {reask}"
    if intent == "scope":
        return (
            "Go as deep as you'd go in a real incident — the actual steps, commands, or trade-offs, "
            f"not just the headline. So: {reask}"
        )
    if intent == "clarify":
        definition = _define_term(candidate_question, question_text)
        lead = f"Let me put it differently. {definition} " if definition else "Let me put it differently. "
        return f"{lead}{reask}"
    # generic
    definition = _define_term(candidate_question, question_text)
    if definition:
        base = f"Fair question. {definition} So, back to it — {reask}"
    else:
        base = f"Fair question — answer it the way you'd explain it to a teammate. {reask}"

    # Optional self-hosted LLM phrasing (audit Y1f). Rules still decide *what*;
    # the LLM only rewrites *how* when FIXITLAB_LLM_GENERATE_URL is set.
    try:
        from .voice_stack import llm_generate_reply

        polished = llm_generate_reply(
            system=(
                "You are a concise technical interviewer. Rewrite the reply below in natural "
                "spoken English (or matching the candidate's language). Keep the same meaning, "
                "keep the re-ask of the original question, under 80 words. No preamble."
            ),
            user=base,
            max_tokens=160,
        )
        if polished and len(polished.strip()) > 20:
            return polished.strip()
    except Exception:  # noqa: BLE001
        pass
    return base


def is_candidate_question(text: str, input_type: str | None = None) -> bool:
    """True when the candidate is asking/interrupting rather than answering (WS5).

    Deliberately strict: long spoken answers that mention a term or end with '?'
    are usually still answers. Only short, explicit meta-requests count."""
    if input_type == "question":
        return True
    low = (text or "").strip().lower()
    if not low:
        return False
    words = low.split()
    word_count = len(words)

    # Strong meta openers — even if the candidate spoke a full sentence.
    strong_meta = (
        "can you repeat", "could you repeat", "say that again", "repeat the question",
        "what was the question", "what do you mean", "what does that mean",
        "can you clarify", "could you clarify", "please clarify",
        "can you explain", "could you explain",
        "i don't understand", "didn't understand", "didn't catch", "did not catch",
        "come again", "one more time",
    )
    if any(p in low for p in strong_meta):
        return True

    # Short interrogatives only — long answers are answers, not interruptions.
    if word_count > 20:
        return False
    if low.startswith(("what is ", "what's ", "what are ", "whats ")):
        return True
    if low.endswith("?") and word_count <= 16:
        if re.match(
            r"^(what|why|how|when|where|which|who|can|could|would|should|"
            r"do|does|did|is|are|was|were|will|sorry|pardon|wait)\b",
            low,
        ):
            return True
    if word_count <= 14:
        soft_meta = ("clarify", "rephrase", "not sure what you mean")
        return any(p in low for p in soft_meta)
    return False


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
    """Return structured score breakdown — fully free, no external API.

    Prefer ``conversation.scorer.compute_semantic_scores`` for new call sites;
    this wrapper keeps the older import path and shares the I1 depth/concrete fix.
    """
    from apps.interviews.services.conversation.scorer import compute_semantic_scores

    return compute_semantic_scores(
        candidate_answer=candidate_answer,
        question_text=question_text,
        round_type=round_type,
        expected_keywords=expected_keywords,
    )


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
