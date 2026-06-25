"""Dynamic, free interview question generation — the PRIMARY question driver.

This module inverts FixitLab's old behaviour where the DB question bank
(``InterviewQuestion``) was the primary source of questions. Here we *generate*
the next question on the fly from:

  * the candidate's LAST answer (quote a phrase / probe a claim / cross-question),
  * a per-round topic agenda seeded from the resume + chosen technology,
  * the chosen tech / seniority level (difficulty framing),
  * the running conversation (so we don't repeat ourselves, and we escalate).

It is 100% FREE and deterministic — no OpenAI/Anthropic or any paid API. Every
decision is rule-based; randomness is from a locally-seeded ``random.Random`` so
the same conversation state yields stable, repeatable output (good for tests).

The DB bank is now a *seed/supplement/safety net* (see ``engine.ask_next_question``):
if it has rows we may occasionally surface a curated one for coverage, but if it
is completely empty the interview still runs fully on generation alone.

Public API:
  * ``plan_round_topics(round_type, profile_snapshot)`` -> ordered topic agenda.
  * ``generate_question(...)`` -> a ``GeneratedQuestion`` for the next turn.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

# Reuse the (already free) topic detector + phrase extractor + stopwords so the
# generator probes on the SAME vocabulary the scorer and human-reply engine use.
from apps.interviews.services.interview_ai import (
    _PHRASE_STOPWORDS,
    _detect_topic,
    _extract_quote_phrase,
    _normalize,
)


# ---------------------------------------------------------------------------
# Per-topic question banks, indexed by difficulty band so harder answers earn
# harder questions. Bands: 1 = warm-up/fundamentals, 2 = working knowledge,
# 3 = production depth, 4-5 = staff-level edge cases & scale.
# These are TEMPLATES the generator composes — not a DB dependency.
# ---------------------------------------------------------------------------

_TOPIC_QUESTIONS: dict[str, dict[int, list[str]]] = {
    "kubernetes": {
        1: [
            "What's the difference between a Deployment and a StatefulSet, and when do you reach for each?",
            "Walk me through what actually happens when you run `kubectl apply` on a Deployment.",
        ],
        2: [
            "A pod is stuck in CrashLoopBackOff. Walk me through your debugging with only kubectl.",
            "How do liveness and readiness probes differ, and what breaks if you misconfigure the readiness one?",
        ],
        3: [
            "40% of a service's pods are OOMKilled but CPU is normal — how do you root-cause it?",
            "How would you do a zero-downtime rollout and what's your automatic rollback trigger?",
        ],
        4: [
            "Design pod scheduling so a noisy tenant can't starve a latency-sensitive one on the same nodes.",
            "Your cluster autoscaler won't add nodes during a spike — walk me through every layer you'd check.",
        ],
    },
    "docker": {
        1: [
            "What's the difference between an image and a container, and where does a layer fit in?",
            "How would you keep a production image small — what goes in, what stays out?",
        ],
        2: [
            "A container exits immediately on start with no logs. How do you find out why?",
            "Walk me through a multi-stage build for a compiled service and why you'd bother.",
        ],
        3: [
            "A long-running container slowly leaks memory in prod. How do you confirm it and contain blast radius?",
            "How do you handle secrets in an image so they never end up baked into a layer?",
        ],
        4: [
            "Design an image build+scan+sign pipeline that blocks a vulnerable base image from ever shipping.",
        ],
    },
    "nginx": {
        1: [
            "What does nginx do as a reverse proxy, and what's an upstream?",
            "How would you reload nginx config without dropping in-flight requests?",
        ],
        2: [
            "You're seeing intermittent 502s only under load. Walk me through diagnosing it end to end.",
            "How would you rate-limit per client without blocking legitimate bursty traffic?",
        ],
        3: [
            "Set up TLS termination plus mutual TLS to an upstream — what are the failure modes?",
            "Half your 502s correlate with deploys. How do you prove it and fix the handoff?",
        ],
    },
    "linux": {
        1: [
            "How do you find which process is eating the most memory right now?",
            "What's the difference between load average and CPU utilisation?",
        ],
        2: [
            "`df` says the disk is fine but writes fail with 'No space left'. What's going on?",
            "A process is stuck in 'D' (uninterruptible sleep). How do you investigate?",
        ],
        3: [
            "Load average is 80 but CPU is 15%. Walk me through your investigation.",
            "How do you find which process is leaking file descriptors, and then prove the fix held?",
        ],
        4: [
            "A box intermittently freezes for seconds under no obvious load. How do you trace it to the kernel?",
        ],
    },
    "monitoring": {
        1: [
            "When would you use a counter vs a gauge vs a histogram in Prometheus?",
            "What's the difference between an SLI, an SLO, and an SLA?",
        ],
        2: [
            "Your on-call is drowning in alerts. How do you cut the noise without missing real incidents?",
            "Define meaningful SLIs and SLOs for a payment API — what do you measure and why?",
        ],
        3: [
            "Metric cardinality just exploded and Prometheus is OOMing. How do you contain it fast and properly?",
            "Design an alert that pages on user-facing impact, not on a single failing replica.",
        ],
    },
    "aws": {
        1: [
            "What's the difference between a security group and a NACL?",
            "When would you pick a managed service over running it yourself on EC2?",
        ],
        2: [
            "An Auto Scaling group is stuck cycling unhealthy instances. How do you debug it?",
            "How do you audit who can touch production in an account with hundreds of IAM roles?",
        ],
        3: [
            "Design cross-region failover for a stateful service with an RTO under 5 minutes.",
            "Costs jumped 40% month over month with no traffic change. How do you find the cause?",
        ],
    },
    "terraform": {
        1: [
            "What does the state file actually do, and why is it dangerous to lose?",
            "What's the difference between `plan` and `apply`, and why review the plan?",
        ],
        2: [
            "The state is locked and the holder is gone. How do you recover safely?",
            "How do you test a Terraform change before it touches production?",
        ],
        3: [
            "There's drift between state and real infra. Walk me through reconciling it without an outage.",
            "How would you structure Terraform across 50 microservices so teams move independently?",
        ],
    },
    "ci_cd": {
        1: [
            "What belongs in CI vs CD, and where's the line for you?",
            "How do you keep secrets out of build logs in a pipeline?",
        ],
        2: [
            "Your CI pipeline has crept to 30+ minutes. How do you bring it down without losing safety?",
            "How would you automatically roll back a bad release the moment error rate spikes?",
        ],
        3: [
            "Design a deploy pipeline with progressive rollout and an automatic, metric-driven abort.",
        ],
    },
    "python": {
        1: [
            "What's the difference between a list and a generator, and when does it matter?",
            "How do you manage dependencies so prod matches what you tested?",
        ],
        2: [
            "A Python service leaks memory over hours. How do you find the leak?",
            "Walk me through profiling a slow Django endpoint and what you'd act on first.",
        ],
        3: [
            "How do you reason about thread safety and the GIL in a high-throughput Python service?",
        ],
    },
    "ansible": {
        1: [
            "What does idempotency mean for a playbook, and why does it matter?",
            "How do you keep secrets out of a playbook without a full Vault setup?",
        ],
        2: [
            "A run partially fails across 200 hosts. How do you recover to a consistent state?",
            "How do you test an Ansible role in CI without a real inventory?",
        ],
    },
    "security": {
        1: [
            "What does least privilege mean in practice for a service account?",
            "How do you handle a CVE in a dependency that's deep in production?",
        ],
        2: [
            "You suspect a credential leaked. Walk me through detecting lateral movement.",
            "Walk me through your incident response for a suspected container escape.",
        ],
        3: [
            "Design defence-in-depth so a single leaked token can't reach customer data.",
        ],
    },
    "database": {
        1: [
            "What's the difference between a primary and a read replica, and when do you add one?",
            "How do you take a backup you actually trust — what do you verify?",
        ],
        2: [
            "How do you run a zero-downtime schema migration on a 500GB table?",
            "Replication lag is climbing under write load. How do you diagnose and mitigate it?",
        ],
        3: [
            "A query is fast in staging and slow in prod. Walk me through finding the real difference.",
        ],
    },
    "networking": {
        1: [
            "Walk me through what happens, layer by layer, when you curl a URL.",
            "What's the difference between a connection refused and a connection timeout?",
        ],
        2: [
            "DNS resolves fine but the service is unreachable from one subnet only. How do you isolate it?",
        ],
    },
}

# Generic technical questions when no topic is detected yet — still difficulty-banded.
_GENERIC_TECH_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Tell me about a system you've operated recently — what was your slice of it?",
        "What's a tool you reach for first when something's broken in production, and why?",
    ],
    2: [
        "Walk me through the last production issue you debugged, start to resolution.",
        "How do you decide what to monitor on a service you own?",
    ],
    3: [
        "Describe the hardest incident you've owned — what made it hard and how did you contain it?",
        "How do you make a risky change to a system you can't take offline?",
    ],
    4: [
        "Design the reliability story for a service that absolutely cannot lose data. Walk me through it.",
        "Where would your current architecture break first at 100x load, and what would you do about it?",
    ],
}

# Open-ended prompts used when the banded generic bank is fully exhausted within a
# round. Distinct enough that we can rotate through several before repeating.
_OPEN_ENDED_FALLBACKS = [
    "Walk me through the most interesting technical problem you've solved recently.",
    "Tell me about a decision you made that you'd defend even though it was unpopular.",
    "Describe a system you built or operated that you're genuinely proud of, and why.",
    "What's a piece of technical debt you've lived with — how did you reason about paying it down?",
    "Talk me through how you'd ramp up on a large, unfamiliar codebase in your first two weeks.",
]

# Rotating "angle" suffixes appended to a base prompt so that, even once the whole
# fallback pool is used in a round, each subsequent question is still unique.
_FALLBACK_ANGLES = [
    "— going one level deeper",
    "— focusing on what you'd do differently now",
    "— walking through the trade-offs",
    "— with the hardest edge case in mind",
]

# Cross-question scaffolds — these QUOTE the candidate's own answer ("you said X")
# and pivot to a harder dimension. {phrase} is a fragment from their last answer.
# Expanded (WS3) with explicit answer-relative angles: failure mode, trade-off,
# what they'd change, how they'd verify — so the FIRST follow-up after a
# substantive answer always has somewhere specific to go.
_CROSS_QUESTION_TEMPLATES = [
    # scale / load
    "You mentioned “{phrase}” — how does that hold up when traffic suddenly doubles?",
    # failure mode
    "You said “{phrase}”. What's the failure mode there, and how would you catch it early?",
    "You leaned on “{phrase}”. What breaks first if that assumption is wrong?",
    "On “{phrase}” — what's the worst-case scenario, and how do you detect it before users do?",
    # trade-off
    "You brought up “{phrase}” — what's the trade-off you're accepting there, and what did you give up?",
    "“{phrase}” has a cost. What's the downside of that choice, and when would it bite you?",
    # what they'd change
    "If you were redoing “{phrase}” from scratch today, what would you do differently and why?",
    "Knowing what you know now, what's the one thing about “{phrase}” you'd change?",
    # how they'd verify
    "After “{phrase}”, how would you actually verify it worked — what signal confirms it?",
    "You said “{phrase}”. How do you know it's healthy — what would you measure right after?",
    # convince / steps / rollback / offline
    "Picking up on “{phrase}” — how would you prove to a skeptical senior that it's the right call?",
    "On “{phrase}” — walk me through the exact steps, command by command.",
    "You brought up “{phrase}”. How would you roll that back if it went sideways mid-deploy?",
    "Let's stress-test “{phrase}”: what would you watch for the first 24 hours after shipping it?",
    "You said “{phrase}” — how does that change if you can't take the system offline?",
]

# Command/code-aware cross-question scaffolds (WS7) — used when the candidate has
# just run/typed a real command or code we validated. {cmd} is their actual
# command/code text so the follow-up quotes what they RAN, probing
# verification / idempotency / rollback / failure.
_COMMAND_CROSS_TEMPLATES = [
    "You ran `{cmd}` — how would you confirm it actually came back healthy?",
    "After `{cmd}`, what's the very next thing you check to know it worked?",
    "Is `{cmd}` safe to run twice? What happens if it's already in the desired state?",
    "If `{cmd}` had failed halfway, how would you tell, and how would you roll back?",
    "`{cmd}` did the job — now how do you make sure it survives a reboot / the next deploy?",
    "What would `{cmd}` look like in its output if something were still wrong underneath?",
    "Walk me through validating `{cmd}` in staging before you'd ever run it in prod.",
    "You used `{cmd}`. What's the blast radius if you'd targeted the wrong host or namespace?",
]

# Tool/entity-aware drills (free cross-questioning) — when the candidate NAMES a
# specific tool/technology in their answer, the interviewer drills into THAT exact
# tool ("You mentioned Ansible — how did you structure your playbooks?"). This is
# what makes the bot feel like it actually heard them. 100% deterministic/local.
# Each entry: canonical tool -> pointed, experience-probing questions.
_TOOL_DRILLS: dict[str, list[str]] = {
    "ansible": [
        "You mentioned Ansible — how did you structure your playbooks and roles?",
        "With Ansible, how did you keep tasks idempotent across reruns?",
        "How did you handle secrets and inventory in your Ansible setup?",
    ],
    "terraform": [
        "You brought up Terraform — how did you manage state and locking across the team?",
        "With Terraform, how did you structure modules so teams could move independently?",
        "How did you test Terraform changes before applying them to production?",
    ],
    "kubernetes": [
        "You mentioned Kubernetes — walk me through how you debugged a failing pod.",
        "With Kubernetes, how did you handle rollouts and rollbacks safely?",
        "How did you set resource requests and limits to avoid noisy-neighbor issues?",
    ],
    "docker": [
        "You mentioned Docker — how did you keep your images small and secure?",
        "With Docker, how did you debug a container that exited right after start?",
    ],
    "prometheus": [
        "You mentioned Prometheus — what metrics did you actually alert on, and why?",
        "With Prometheus, how did you deal with metric cardinality?",
    ],
    "grafana": [
        "You mentioned Grafana — what did your most-used dashboard actually show?",
        "How did you decide what belonged on a dashboard versus an alert?",
    ],
    "jenkins": [
        "You mentioned Jenkins — how was your pipeline structured, and where did it get slow?",
        "With Jenkins, how did you keep secrets out of build logs?",
    ],
    "git": [
        "You mentioned Git — what branching/merge strategy did your team actually use?",
        "Tell me about a nasty merge or rebase situation you had to untangle.",
    ],
    "nginx": [
        "You mentioned nginx — how did you reload config without dropping requests?",
        "Walk me through how you debugged a 502 behind nginx.",
    ],
    "redis": [
        "You mentioned Redis — what did you use it for, and how did you handle eviction?",
        "How did you reason about Redis persistence and failover?",
    ],
    "postgres": [
        "You mentioned Postgres — how did you find and fix a slow query in production?",
        "How did you run a schema migration without downtime?",
    ],
    "kafka": [
        "You mentioned Kafka — how did you handle consumer lag and rebalancing?",
        "How did you reason about partitioning and ordering guarantees?",
    ],
    "aws": [
        "You mentioned AWS — which services specifically, and what did you own there?",
        "How did you keep AWS costs and IAM sprawl under control?",
    ],
    "python": [
        "You mentioned Python — what did you build with it, and how did you test it?",
        "Tell me about debugging a memory or performance issue in a Python service.",
    ],
    "bash": [
        "You mentioned shell scripting — walk me through the trickiest script you wrote.",
        "How did you make your shell scripts safe to rerun and fail loudly?",
    ],
    "helm": [
        "You mentioned Helm — how did you manage chart versions and upgrades safely?",
    ],
    "argocd": [
        "You mentioned ArgoCD — how did your GitOps sync and rollback flow work?",
    ],
    "vault": [
        "You mentioned Vault — how did services actually authenticate and fetch secrets?",
    ],
    "elk": [
        "You mentioned the ELK/logging stack — how did you control log volume and cost?",
    ],
    "datadog": [
        "You mentioned Datadog — what did you actually monitor, and how did you tame the bill?",
        "How did you cut alert noise in Datadog without missing real incidents?",
    ],
    "splunk": [
        "You mentioned Splunk — walk me through a query you leaned on during an incident.",
    ],
    "mongodb": [
        "You mentioned MongoDB — how did you handle schema design and indexing for it?",
        "How did you reason about replica sets and failover in Mongo?",
    ],
    "mysql": [
        "You mentioned MySQL — how did you find and fix a slow query in production?",
        "How did you handle replication lag under heavy writes?",
    ],
    "rabbitmq": [
        "You mentioned RabbitMQ — how did you handle dead letters and retries?",
        "How did you reason about acknowledgements and at-least-once delivery?",
    ],
    "istio": [
        "You mentioned Istio — what did the service mesh actually buy you, and what did it cost?",
        "How did you debug a request failing somewhere inside the mesh?",
    ],
    "cicd": [
        "You mentioned your CI/CD pipeline — walk me through its stages and where it got slow.",
        "How did you make a bad release roll back automatically?",
        "How did you keep secrets out of the pipeline and its logs?",
    ],
    "golang": [
        "You mentioned Go — how did you handle concurrency with goroutines and channels there?",
        "Tell me about debugging a goroutine leak or a race in a Go service.",
    ],
    "java": [
        "You mentioned Java — how did you diagnose a GC or heap problem in production?",
        "How did you reason about thread pools and back-pressure in your Java service?",
    ],
    "nodejs": [
        "You mentioned Node — how did you keep the event loop from blocking under load?",
        "Tell me about debugging a memory leak in a long-running Node process.",
    ],
    "flux": [
        "You mentioned Flux — how did your GitOps reconciliation and rollback flow work?",
    ],
}

# Alias -> canonical tool. Detection scans the candidate's answer for these.
_TOOL_ALIASES: dict[str, str] = {
    "ansible": "ansible", "playbook": "ansible", "playbooks": "ansible",
    "terraform": "terraform", "tofu": "terraform", "opentofu": "terraform",
    "kubernetes": "kubernetes", "k8s": "kubernetes", "kubectl": "kubernetes", "eks": "kubernetes", "gke": "kubernetes", "aks": "kubernetes",
    "docker": "docker", "dockerfile": "docker", "containerd": "docker",
    "prometheus": "prometheus", "promql": "prometheus", "alertmanager": "prometheus",
    "grafana": "grafana",
    "jenkins": "jenkins",
    "git": "git", "github": "git", "gitlab": "git",
    "nginx": "nginx",
    "redis": "redis",
    "postgres": "postgres", "postgresql": "postgres", "psql": "postgres",
    "kafka": "kafka",
    "aws": "aws", "ec2": "aws", "s3": "aws", "lambda": "aws", "cloudwatch": "aws",
    "python": "python", "django": "python", "flask": "python", "fastapi": "python",
    "bash": "bash", "shell script": "bash", "shell scripting": "bash",
    "helm": "helm",
    "argocd": "argocd", "argo cd": "argocd",
    "vault": "vault",
    "elk": "elk", "elasticsearch": "elk", "logstash": "elk", "kibana": "elk",
    "datadog": "datadog",
    "splunk": "splunk",
    "mongodb": "mongodb", "mongo": "mongodb",
    "mysql": "mysql", "mariadb": "mysql",
    "rabbitmq": "rabbitmq", "rabbit mq": "rabbitmq",
    "istio": "istio", "service mesh": "istio", "linkerd": "istio",
    "github actions": "cicd", "gitlab ci": "cicd", "circleci": "cicd",
    "golang": "golang", "go lang": "golang",
    "java": "java", "jvm": "java",
    "nodejs": "nodejs", "node.js": "nodejs", "node js": "nodejs",
    "flux": "flux", "fluxcd": "flux",
}

# Topic-drill scaffolds — go deeper on the topic the candidate is clearly in,
# without necessarily quoting a phrase.
_TOPIC_DRILL_TEMPLATES = [
    "Let's go one level deeper on {topic}: {q}",
    "Staying on {topic} — {q}",
    "Good, now the harder version: {q}",
    "Alright, {topic} again but trickier: {q}",
]

# Discussion / opinion turns — make it a conversation, not a quiz. Used sparingly.
_DISCUSSION_TEMPLATES = [
    "Let's just talk shop for a sec — where do you land on {topic}: what's overrated and what's underrated?",
    "Off the script for a moment: what's a {topic} take you hold that a lot of engineers would push back on?",
    "Honest question — what part of {topic} do you actually enjoy, and what do you avoid?",
]

# Real-interview opening (WS4): warm-up questions a human interviewer actually
# opens with — "tell me about yourself", then most-recent-role / experience —
# served BEFORE any technical drilling. {role}/{company} are filled from the
# profile snapshot when available, with graceful generic fallbacks.
_INTRO_QUESTIONS = [
    "To start, tell me about yourself and your background — how'd you get into this work?",
    "Walk me through your most recent role — what were you responsible for day to day?",
    "Give me the quick version of your experience so far — what have you spent the most time on?",
    "Before we dig in, tell me what you're working on right now and what drew you to this {role} track.",
    "Let's start easy — what does a typical week look like in your current role at {company}?",
]

# Light personal / fun slot for HR rounds (WS4) — keeps the opening human.
_PERSONAL_QUESTIONS = [
    "Outside of work, what do you geek out on — any side projects or hobbies?",
    "What's something you're genuinely excited about in tech right now?",
    "How do you like to recharge after a rough on-call week?",
    "What first got you hooked on this field?",
    "If you weren't doing this, what do you imagine you'd be doing instead?",
]

# Behavioral / situational (HR + manager + leadership). Difficulty-banded.
_BEHAVIORAL_QUESTIONS: dict[int, list[str]] = {
    1: [
        "Tell me about a time you fixed something under pressure. What did you do?",
        "Walk me through a project you're proud of — what was your specific role?",
    ],
    2: [
        "Tell me about a disagreement with a teammate on a technical decision. How did it resolve?",
        "Describe a time you owned a mistake in production. What happened next?",
    ],
    3: [
        "Tell me about a time you had to push back on a deadline. How did you handle the stakeholders?",
        "Describe leading an incident where information was incomplete. How did you make the call?",
    ],
    4: [
        "Tell me about a time you changed the technical direction of a team without formal authority.",
    ],
}

_HR_QUESTIONS: dict[int, list[str]] = {
    1: [
        "What's driving your search right now — growth, comp, tech stack, something else?",
        "What does your ideal team culture actually look like day to day?",
    ],
    2: [
        "What would make you say yes to an offer in the next few weeks?",
        "Tell me about a manager who got the best out of you — what did they do?",
    ],
    3: [
        "Where do you want to be in two years, and how does this role fit that?",
        "What's a piece of feedback that changed how you work?",
    ],
}

_MANAGER_QUESTIONS: dict[int, list[str]] = {
    1: [
        "How do you decide when to escalate an incident versus handle it yourself?",
        "What does a useful, blameless postmortem look like to you?",
    ],
    2: [
        "Two P1s are firing at once with one on-call. How do you triage?",
        "How do you keep a cross-functional team aligned during a long outage?",
    ],
    3: [
        "A vendor is in your blast radius and breaching SLA. Who owns the clock, and what do you do?",
        "How do you classify a change — standard, normal, or emergency — and why does it matter?",
    ],
}

# Light openers that acknowledge the candidate's last answer before the next
# question, so a generated question doesn't feel like a survey form (FIX 3:
# conversational delivery + natural transitions). Kept distinct from
# interview_ai's reply acks (the engine uses that for the *reply*; these are
# short spoken stitches on the *question* turn). Varied so a long round of
# generated questions never reads like reading a quiz aloud.
_QUESTION_STITCHES = [
    "Okay.",
    "Right.",
    "Got it.",
    "Makes sense.",
    "Cool.",
    "Fair.",
    "Alright.",
    "Sure.",
    "Okay, good.",
    "Right, let's keep going.",
    "Mm-hm.",
    "Nice.",
    "Let's switch gears.",
    "Okay, next.",
    "Good — moving on.",
    "Let me change tack.",
]

# Round type -> behavioral/situational bank to use.
_ROUND_BEHAVIORAL_BANK = {
    "hr": _HR_QUESTIONS,
    "manager": _MANAGER_QUESTIONS,
    "leadership": _BEHAVIORAL_QUESTIONS,
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class GeneratedQuestion:
    """A dynamically generated question for the next turn.

    Mirrors the fields ``engine.ask_next_question`` needs to persist an
    ``InterviewMessage`` *without* a DB ``InterviewQuestion`` row. ``category``
    and ``practical_config`` go into message metadata so the frontend (which
    keys off ``message_type`` + ``metadata.practical_config``) renders it
    exactly like a banked question.
    """

    text: str
    category: str = "technical"
    topic: str | None = None
    difficulty: int = 2
    kind: str = "generated"  # generated | followup | cross | drill | discussion | behavioral
    practical_config: dict = field(default_factory=dict)

    @property
    def message_type(self) -> str:
        return "practical" if self.category == "practical" else "question"


# ---------------------------------------------------------------------------
# Resume / round → topic agenda
# ---------------------------------------------------------------------------

# Map free-text resume skills / tech names onto our canonical topic keys.
_SKILL_TO_TOPIC = {
    "kubernetes": "kubernetes", "k8s": "kubernetes", "kubectl": "kubernetes", "helm": "kubernetes",
    "docker": "docker", "container": "docker", "compose": "docker",
    "nginx": "nginx", "apache": "nginx", "httpd": "nginx", "load balancer": "nginx",
    "linux": "linux", "rhel": "linux", "ubuntu": "linux", "centos": "linux", "bash": "linux", "shell": "linux",
    "prometheus": "monitoring", "grafana": "monitoring", "datadog": "monitoring", "splunk": "monitoring", "elk": "monitoring",
    "aws": "aws", "ec2": "aws", "s3": "aws", "eks": "aws", "cloud": "aws", "azure": "aws", "gcp": "aws",
    "terraform": "terraform",
    "ansible": "ansible",
    "jenkins": "ci_cd", "ci/cd": "ci_cd", "gitlab": "ci_cd", "argocd": "ci_cd", "github actions": "ci_cd",
    "python": "python", "django": "python", "flask": "python",
    "security": "security", "vault": "security", "firewall": "networking", "vpn": "networking",
    "mysql": "database", "postgres": "database", "mongodb": "database", "redis": "database", "kafka": "database",
    "networking": "networking", "tcp/ip": "networking", "dns": "networking",
}

# When a round wants depth but the resume yielded nothing, fall back to a
# sensible default agenda per round type so we always have somewhere to go.
_DEFAULT_TOPIC_AGENDA = ["linux", "kubernetes", "monitoring", "ci_cd"]


def _topics_from_snapshot(profile_snapshot: dict) -> list[str]:
    """Extract an ordered, de-duped list of canonical topics from the resume +
    chosen technologies. Primary technology first, then resume skills, then
    secondary technologies."""
    snap = profile_snapshot or {}
    ordered: list[str] = []

    def add(raw: str):
        if not raw:
            return
        low = str(raw).lower().strip()
        topic = _SKILL_TO_TOPIC.get(low)
        if not topic:
            # substring match (e.g. "amazon web services" -> nothing; "k8s ops" -> kubernetes)
            for key, t in _SKILL_TO_TOPIC.items():
                if key in low:
                    topic = t
                    break
        if topic and topic not in ordered:
            ordered.append(topic)

    add(snap.get("primary_technology_name"))

    parsed = snap.get("resume_parsed") or {}
    for skill in (parsed.get("skills_detected") or []):
        add(skill)

    for tech in (snap.get("secondary_technologies") or []):
        add(tech)

    return ordered


def plan_round_topics(round_type: str, profile_snapshot: dict) -> list[str]:
    """Ordered topic agenda for a round, seeded from the resume + chosen tech.

    Non-technical rounds (hr) don't drill technical topics, so they get an empty
    agenda (the generator falls back to behavioral/situational banks). Technical
    and deep-dive rounds get the resume-derived agenda (or a sane default)."""
    if round_type in ("hr",):
        return []
    topics = _topics_from_snapshot(profile_snapshot)
    if not topics:
        return list(_DEFAULT_TOPIC_AGENDA)
    # Deep-dive deliberately reverses to revisit strengths/gaps differently than R1.
    if round_type == "deep_dive":
        topics = list(reversed(topics))
    return topics


def starting_difficulty(profile_snapshot: dict) -> int:
    """Seniority/years-aware starting difficulty (1-5)."""
    snap = profile_snapshot or {}
    level = (snap.get("experience_level") or "mid").lower()
    base = {"junior": 1, "mid": 2, "senior": 3, "lead": 4}.get(level, 2)
    parsed = snap.get("resume_parsed") or {}
    # Years may arrive as a non-numeric hint ("7 years", "5+", "ten") — extract the
    # first integer defensively and default to 0 instead of raising ValueError.
    raw_years = parsed.get("years_experience_hint") or snap.get("years_experience") or 0
    m = re.search(r"\d+", str(raw_years))
    years = int(m.group()) if m else 0
    if years >= 10:
        base = max(base, 4)
    elif years >= 6:
        base = max(base, 3)
    return max(1, min(5, base))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _band(difficulty: int, available: dict[int, list]) -> int:
    """Snap a difficulty (1-5) onto the nearest band we actually have content for."""
    d = max(1, min(5, int(difficulty or 2)))
    if d in available:
        return d
    # walk down then up to find the closest populated band
    for delta in range(1, 5):
        if d - delta in available:
            return d - delta
        if d + delta in available:
            return d + delta
    return next(iter(available))


def _pick(options: list[str], used: set[str], rng: random.Random) -> str | None:
    """Pick an option whose normalized form isn't already used this round."""
    if not options:
        return None
    shuffled = options[:]
    rng.shuffle(shuffled)
    for opt in shuffled:
        if _normalize(opt) not in used:
            return opt
    return None  # everything used — caller decides what to do


def _topic_question(topic: str, difficulty: int, used: set[str], rng: random.Random) -> str | None:
    bank = _TOPIC_QUESTIONS.get(topic)
    if not bank:
        return None
    band = _band(difficulty, bank)
    # Try the target band, then adjacent bands, so a long round on one topic
    # doesn't dead-end once the ideal band is exhausted.
    for b in (band, min(5, band + 1), max(1, band - 1), min(5, band + 2)):
        q = _pick(bank.get(b, []), used, rng)
        if q:
            return q
    return None


def _generic_question(difficulty: int, used: set[str], rng: random.Random) -> str | None:
    band = _band(difficulty, _GENERIC_TECH_QUESTIONS)
    for b in (band, min(4, band + 1), max(1, band - 1)):
        q = _pick(_GENERIC_TECH_QUESTIONS.get(b, []), used, rng)
        if q:
            return q
    # absolute last resort — still honor `used` so we return None when everything
    # is genuinely exhausted, letting the caller vary instead of repeating verbatim.
    return _pick([x for xs in _GENERIC_TECH_QUESTIONS.values() for x in xs], used, rng)


def _behavioral_question(round_type: str, difficulty: int, used: set[str], rng: random.Random) -> str | None:
    bank = _ROUND_BEHAVIORAL_BANK.get(round_type, _BEHAVIORAL_QUESTIONS)
    band = _band(difficulty, bank)
    for b in (band, min(4, band + 1), max(1, band - 1), min(4, band + 2)):
        q = _pick(bank.get(b, []), used, rng)
        if q:
            return q
    return _pick([x for xs in bank.values() for x in xs], set(), rng)


def _intro_question(
    *,
    profile_snapshot: dict,
    category_preference: str | None,
    questions_asked: int,
    personal_slot: bool,
    used: set[str],
    rng: random.Random,
) -> str | None:
    """Serve a warm-up opening question (WS4): 'tell me about yourself', then
    most-recent-role/experience, then (HR only) an optional personal/fun slot.

    Free/local. {role}/{company} are filled from the snapshot with safe generic
    fallbacks so a missing field never breaks formatting."""
    snap = profile_snapshot or {}
    role = snap.get("target_role") or snap.get("experience_level") or "this"
    company = snap.get("current_company") or "your current company"

    def fmt(q: str) -> str:
        try:
            return q.format(role=role, company=company)
        except (KeyError, IndexError, ValueError):
            return q

    if personal_slot:
        q = _pick(_PERSONAL_QUESTIONS, used, rng)
        if q:
            return fmt(q)

    # Deterministically prefer the very first warm-up on question 0 so the round
    # always opens with "tell me about yourself", then most-recent-role on Q1.
    if questions_asked == 0 and _normalize(fmt(_INTRO_QUESTIONS[0])) not in used:
        return fmt(_INTRO_QUESTIONS[0])
    if questions_asked == 1 and _normalize(fmt(_INTRO_QUESTIONS[1])) not in used:
        return fmt(_INTRO_QUESTIONS[1])
    q = _pick([fmt(x) for x in _INTRO_QUESTIONS], used, rng)
    return q


def _command_cross_question(
    last_command: str, used: set[str], rng: random.Random
) -> str | None:
    """WS7: quote the candidate's actual validated command/code in the next
    question, probing verification/idempotency/rollback/failure. Returns None if
    there's no usable command text."""
    cmd = (last_command or "").strip()
    if not cmd:
        return None
    # Keep the quoted command to a single readable line/fragment.
    cmd = re.split(r"[\n\r]", cmd, 1)[0].strip()
    if len(cmd) > 120:
        cmd = cmd[:117] + "…"
    if not cmd:
        return None
    tpl = _pick(_COMMAND_CROSS_TEMPLATES, used, rng) or _COMMAND_CROSS_TEMPLATES[0]
    text = tpl.format(cmd=cmd)
    if _normalize(text) in used:
        return None
    return text


def _detect_mentioned_tools(text: str) -> list[str]:
    """Return canonical tools the candidate NAMED in their answer, in the order
    they appear, de-duped. Free/local — word-boundary alias matching."""
    if not text:
        return []
    low = f" {text.lower()} "
    found: list[str] = []
    for alias, canonical in _TOOL_ALIASES.items():
        # Word-boundary match so 'aws' doesn't fire inside 'awesome'.
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", low):
            if canonical not in found:
                found.append(canonical)
    return found


def _tool_cross_question(
    last_answer: str, used: set[str], rng: random.Random
) -> tuple[str, str] | None:
    """Pick a pointed drill question about a SPECIFIC tool the candidate just
    named (e.g. 'You mentioned Ansible — how did you structure your playbooks?').

    Returns (question_text, canonical_tool) or None. Honors ``used`` so we never
    repeat a drill, and naturally rotates to a different tool once one's drills
    are exhausted."""
    tools = _detect_mentioned_tools(last_answer)
    if not tools:
        return None
    # Slight shuffle so two answers naming the same tools don't always drill the
    # first one — but keep it deterministic via the seeded rng.
    rng.shuffle(tools)
    for tool in tools:
        q = _pick(_TOOL_DRILLS.get(tool, []), used, rng)
        if q:
            return q, tool
    return None


def _seed_from(conversation_tail: list[dict], questions_asked: int) -> int:
    """Deterministic seed: stable for a given conversation state so output is
    repeatable (tests) but varies turn-to-turn (not robotic)."""
    blob = "".join((m.get("content") or "")[:40] for m in (conversation_tail or []))
    return (hash(blob) ^ (questions_asked * 2654435761)) & 0x7FFFFFFF


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_question(
    *,
    round_type: str,
    profile_snapshot: dict,
    difficulty: int,
    questions_asked: int,
    last_answer: str = "",
    last_answer_quality: str = "",
    topic_agenda: list[str] | None = None,
    asked_texts: list[str] | None = None,
    conversation_tail: list[dict] | None = None,
    strong_streak: int = 0,
    category_preference: str | None = None,
    last_command: str = "",
    turns_since_last_cross: int = 99,
    system_design_prompt: str = "",
    system_design_phase: str = "",
    memory: dict | None = None,
    seconds_left: float | None = None,
    active_incident: dict | None = None,
    last_question_kind: str = "",
    last_practical_config: dict | None = None,
) -> GeneratedQuestion:
    """Generate the next interview question dynamically. Always returns a
    ``GeneratedQuestion`` — generation never returns ``None`` (that's the whole
    point of inverting the bank: the interview always has somewhere to go).

    Decision order (free + deterministic):

      0. WARM-UP OPENING (WS4): for the opening slots (category_preference in
         intro/experience/personal) serve a human opener — "tell me about
         yourself", then most-recent-role/experience — BEFORE technical drilling.
      0b. COMMAND/CODE FOLLOW-UP (WS7): if the candidate just ran a validated
         command/code (``last_command``), quote what they RAN and probe
         verification / idempotency / rollback / failure.
      1. If the candidate's last answer was substantive, CROSS-QUESTION it: quote
         a phrase they used and pivot to a harder dimension. GUARANTEED (WS3) for
         the FIRST follow-up after that answer (``turns_since_last_cross``),
         probabilistic afterwards so we don't quiz every single turn. After a
         strong streak, escalate harder.
      2. Otherwise, or on a rotation, DRILL the current resume/round topic at the
         adapted difficulty (topic-specific bank).
      3. Occasionally open a DISCUSSION turn (opinion/trade-off) to feel human.
      4. For HR / behavioral / situational slots, pull from the behavioral bank.
      5. Fall back to a generic technical question — never a dead end.

    ``category_preference`` (from the existing ``round_category_mix``) nudges
    intro/experience/personal vs behavioral/casual vs technical, preserving the
    round's shape. ``last_command`` carries the candidate's actual validated
    command/code text (WS7). ``turns_since_last_cross`` lets the caller avoid
    cross-questioning on every turn while still guaranteeing the first follow-up.
    """
    snap = profile_snapshot or {}
    asked_texts = asked_texts or []
    conversation_tail = conversation_tail or []
    used = {_normalize(t) for t in asked_texts}
    mem = memory if isinstance(memory, dict) else {}

    rng = random.Random(_seed_from(conversation_tail, questions_asked))

    from apps.interviews.services.conversation_intelligence import (
        claim_cross_question,
        detect_contradiction,
        generate_contradiction_probe,
        generate_thread_callback,
        suggest_answer_mode,
        time_pressure_stitch,
        weakest_topic,
    )

    answer_mode = suggest_answer_mode(mem)
    time_stitch = time_pressure_stitch(seconds_left, used, rng)

    def _personalize(text: str) -> str:
        from apps.interviews.services.resume_context import personalize_question
        return personalize_question(text, snap, rng)

    def _finalize(text: str) -> str:
        return _personalize(text)

    incident_round = round_type in ("devops_debug", "sre_oncall")

    # Effective difficulty escalates with a strong streak (cross-checks the
    # engine's own difficulty bump so framing gets harder even mid-round).
    eff_difficulty = int(difficulty or 2)
    if strong_streak >= 4:
        eff_difficulty = min(5, eff_difficulty + 2)
    elif strong_streak >= 2:
        eff_difficulty = min(5, eff_difficulty + 1)

    # --- 0. WARM-UP OPENING (WS4) — real interviews start human, not with a drill.
    intro_slot = category_preference in ("intro", "experience", "personal")
    personal_slot = category_preference == "personal"
    if intro_slot:
        iq = _intro_question(
            profile_snapshot=snap,
            category_preference=category_preference,
            questions_asked=questions_asked,
            personal_slot=personal_slot,
            used=used,
            rng=rng,
        )
        if iq and _normalize(iq) not in used:
            return GeneratedQuestion(
                text=_finalize(iq),
                category="casual",
                topic=None,
                difficulty=1,
                kind="intro",
            )

    # --- 0b. LIVE CODING follow-ups (edge cases, complexity, tests). ---
    lc_config = last_practical_config if isinstance(last_practical_config, dict) else {}
    if (
        round_type == "live_coding"
        and last_question_kind == "live_coding"
        and last_answer
        and not intro_slot
        and category_preference != "practical"
    ):
        from apps.interviews.services.live_coding import generate_followup

        title = lc_config.get("coding_title") or "this exercise"
        signals = lc_config.get("expected_signals") or []
        phase = lc_config.get("live_coding_phase") or "edge_case"
        follow = generate_followup(
            last_answer=last_answer,
            coding_title=title,
            expected_signals=signals,
            phase=phase,
            used=used,
            rng=rng,
        )
        if follow:
            text, next_phase, patch = follow
            cfg = {**lc_config, **patch}
            return GeneratedQuestion(
                text=_finalize(text),
                category="technical",
                topic="linux",
                difficulty=eff_difficulty,
                kind="live_coding_followup",
                practical_config=cfg,
            )

    # --- 0c. LIVE CODING — starter problems (free, no LLM). ---
    if category_preference == "practical" and round_type == "live_coding" and not intro_slot:
        from apps.interviews.services.live_coding import generate_opening

        opened = generate_opening(used=used, rng=rng, difficulty=eff_difficulty)
        if opened:
            text, config = opened
            return GeneratedQuestion(
                text=_finalize(text),
                category="practical",
                topic="linux",
                difficulty=eff_difficulty,
                kind="live_coding",
                practical_config=config,
            )

    # --- 0d. SYSTEM DESIGN (free dimension drilling — no LLM/API). ---
    if category_preference == "system_design":
        from apps.interviews.services.system_design import generate_system_design_question

        text, phase, kind = generate_system_design_question(
            last_answer=last_answer,
            active_prompt=system_design_prompt,
            phase=system_design_phase or None,
            difficulty=eff_difficulty,
            used=used,
            rng=rng,
            questions_asked=questions_asked,
        )
        prompt_key = system_design_prompt
        if kind == "system_design_open":
            prompt_key = text.split(".")[0][:160]
        return GeneratedQuestion(
            text=_finalize(text),
            category="system_design",
            topic="system_design",
            difficulty=eff_difficulty,
            kind=kind,
            practical_config={
                "design_prompt": prompt_key,
                "design_phase": phase,
            },
        )

    # --- 0d. INCIDENT / ON-CALL scenarios (progressive clues — no LLM/API). ---
    incident_slot = (
        category_preference in ("scenario", "troubleshooting", "sla", "itil")
        or incident_round
    )
    if incident_slot and not intro_slot:
        from apps.interviews.services.incident_scenarios import generate_incident_turn, pick_scenario

        inc = active_incident if isinstance(active_incident, dict) else {}
        scenario = inc.get("scenario")
        if not scenario:
            scenario = pick_scenario(used, rng, round_type=round_type)
            inc = {"title": scenario["title"], "revealed": 0, "phase": "open"}
        text, revealed, phase = generate_incident_turn(
            scenario=scenario,
            last_answer=last_answer,
            revealed_clues=int(inc.get("revealed", 0)),
            phase=inc.get("phase", "open"),
            used=used,
            rng=rng,
            time_stitch=time_stitch,
            round_type=round_type,
        )
        return GeneratedQuestion(
            text=_finalize(text),
            category="scenario",
            topic=_detect_topic(text) or "kubernetes",
            difficulty=eff_difficulty,
            kind="incident",
            practical_config={
                "incident_title": scenario.get("title"),
                "incident_revealed": revealed,
                "incident_phase": phase,
                "incident_scenario": scenario,
            },
        )

    # What topic is the candidate clearly engaged in right now? Prefer the topic
    # detected from their last answer; otherwise walk the resume/round agenda.
    agenda = topic_agenda if topic_agenda is not None else plan_round_topics(round_type, snap)
    answer_topic = _detect_topic(last_answer) if last_answer else None
    agenda_topic = agenda[questions_asked % len(agenda)] if agenda else None
    current_topic = answer_topic or agenda_topic

    behavioral_slot = (
        round_type == "hr"
        or category_preference in ("behavioral", "casual")
    )

    substantive = bool(last_answer) and last_answer_quality not in ("skipped", "brief", "")
    phrase = _extract_quote_phrase(last_answer) if substantive else None

    # --- CONVERSATIONAL ENGINE — grounded follow-ups from the candidate's words. ---
    if substantive and not intro_slot and not behavioral_slot and last_answer:
        from apps.interviews.services.conversation import (
            analyze_answer,
            decide_next_move,
            generate_follow_up_question,
        )
        from apps.interviews.services.conversation.memory import CampaignMemory
        from apps.interviews.services.conversation.policy import NextMove

        last_q_text = ""
        for turn in reversed(conversation_tail):
            if turn.get("role") == "interviewer":
                last_q_text = turn.get("content") or ""
                break

        analysis = analyze_answer(answer_text=last_answer, question_text=last_q_text)
        camp_mem = CampaignMemory.from_dict(mem.get("campaign_memory") or mem)
        brief_streak = int(mem.get("brief_streak", 0))
        if last_answer_quality in ("brief", "weak"):
            brief_streak += 1
        else:
            brief_streak = 0

        decision = decide_next_move(
            analysis=analysis,
            memory=camp_mem,
            strong_streak=strong_streak,
            brief_streak=brief_streak,
        )
        if decision.move != NextMove.NEW_TOPIC:
            ack, follow_q = generate_follow_up_question(
                analysis=analysis,
                decision=decision,
                used_texts=used,
                rng=rng,
            )
            if follow_q:
                text = f"{ack} {follow_q}".strip()
                if time_stitch:
                    text = f"{time_stitch} {text}".strip()
                kind_map = {
                    NextMove.DRILL_DOWN: "conversational_drill",
                    NextMove.CLARIFY: "conversational_clarify",
                    NextMove.CHALLENGE: "conversational_challenge",
                    NextMove.SCENARIO_ESCALATE: "conversational_escalate",
                    NextMove.EASE_REDIRECT: "conversational_ease",
                    NextMove.HINT_THEN_MOVE: "conversational_hint",
                    NextMove.ANSWER_CANDIDATE: "conversational_answer",
                    NextMove.THREAD_BACK: "conversational_thread",
                }
                return GeneratedQuestion(
                    text=_finalize(text),
                    category="troubleshooting",
                    topic=current_topic,
                    difficulty=eff_difficulty,
                    kind=kind_map.get(decision.move, "conversational"),
                )

    # --- 0a. CONVERSATION MEMORY — thread back to earlier phrases/claims (~20%). ---
    if not intro_slot and questions_asked >= 3 and rng.random() < 0.22:
        if answer_mode == "deep" or int(mem.get("strong_streak", 0)) >= 2:
            contradiction = detect_contradiction(mem, last_answer)
            if contradiction:
                text = generate_contradiction_probe(contradiction, used, rng)
                return GeneratedQuestion(
                    text=_finalize(text),
                    category="scenario",
                    topic=current_topic,
                    difficulty=eff_difficulty,
                    kind="consistency",
                )
            cq = claim_cross_question(mem, used, rng)
            if cq:
                text = f"{time_stitch} {cq}".strip() if time_stitch else cq
                return GeneratedQuestion(
                    text=_finalize(text),
                    category="troubleshooting",
                    topic=current_topic,
                    difficulty=eff_difficulty,
                    kind="cross",
                )
        thread = generate_thread_callback(mem, used, rng)
        if thread:
            text = f"{time_stitch} {thread}".strip() if time_stitch else thread
            return GeneratedQuestion(
                text=_finalize(text),
                category="scenario",
                topic=current_topic,
                difficulty=eff_difficulty,
                kind="thread",
            )

    # Narrow mode: candidate keeps giving brief answers — ask a focused single-step question.
    if answer_mode == "narrow" and current_topic and not behavioral_slot and rng.random() < 0.45:
        narrow_band = max(1, eff_difficulty - 1)
        nq = _topic_question(current_topic, narrow_band, used, rng)
        if nq:
            text = f"{time_stitch} Let's focus on one step: {nq}".strip() if time_stitch else f"Let's focus on one step: {nq}"
            return GeneratedQuestion(
                text=_finalize(text),
                category="technical",
                topic=current_topic,
                difficulty=narrow_band,
                kind="narrow",
            )

    # Underexplored agenda topic — steer toward a gap in resume coverage.
    if not intro_slot and agenda and questions_asked >= 4 and rng.random() < 0.25:
        gap_topic = weakest_topic(mem, agenda)
        if gap_topic and gap_topic != current_topic:
            gq = _topic_question(gap_topic, eff_difficulty, used, rng)
            if gq:
                text = f"{time_stitch} We haven't touched {gap_topic.replace('_', '/')} much — {gq}".strip()
                return GeneratedQuestion(
                    text=_finalize(text),
                    category="technical",
                    topic=gap_topic,
                    difficulty=eff_difficulty,
                    kind="agenda",
                )

    # --- 0b. COMMAND/CODE FOLLOW-UP (WS7) — quote what they actually RAN. ---
    # When a practical command/code answer was validated, the very next question
    # should reference it ("you ran `systemctl restart sshd` — how would you
    # confirm it came back healthy?"). Highest priority follow-up so the hands-on
    # work directly drives the conversation, even in a behavioral slot.
    if last_command:
        cq = _command_cross_question(last_command, used, rng)
        if cq:
            return GeneratedQuestion(
                text=_finalize(cq),
                category="troubleshooting",
                topic=current_topic or _detect_topic(last_command),
                difficulty=eff_difficulty,
                kind="cross",
            )

    # --- 1a. TOOL-AWARE CROSS-QUESTION (strongest "I heard you" move). ---
    # If the candidate NAMED a specific tool (Ansible, Terraform, Prometheus…),
    # drill into THAT exact tool by name before any generic phrase-based cross.
    # Guaranteed on the first follow-up after a substantive answer; probabilistic
    # afterwards so we don't drill tools every single turn.
    if substantive and not behavioral_slot and not intro_slot:
        first_followup = turns_since_last_cross >= 1
        if first_followup or rng.random() < (0.7 if last_answer_quality == "strong" else 0.5):
            tool_cq = _tool_cross_question(last_answer, used, rng)
            if tool_cq:
                text, tool = tool_cq
                stitch = _maybe_stitch(last_answer_quality, rng)
                text = f"{stitch} {text}".strip() if stitch else text
                return GeneratedQuestion(
                    text=_finalize(text),
                    category="troubleshooting",
                    topic=_SKILL_TO_TOPIC.get(tool) or current_topic,
                    difficulty=eff_difficulty,
                    kind="cross",
                )

    # --- 1. CROSS-QUESTION the candidate's own answer (primary human move). ---
    # WS3: when we have a quotable phrase in a technical-ish slot, ALWAYS cross
    # for the FIRST follow-up after that answer (turns_since_last_cross >= 1).
    # Afterwards keep it probabilistic so we don't quiz on every single turn.
    if phrase and not behavioral_slot:
        first_followup = turns_since_last_cross >= 1
        if first_followup:
            cross = True
        else:
            cross_chance = 0.75 if last_answer_quality == "strong" else 0.55
            cross = rng.random() < cross_chance
        if cross:
            tpl = _pick(_CROSS_QUESTION_TEMPLATES, used, rng)
            # Guaranteed path: if every template is used this round, reuse the
            # first one anyway so the first follow-up still quotes them (WS3).
            if tpl is None and first_followup:
                tpl = _CROSS_QUESTION_TEMPLATES[questions_asked % len(_CROSS_QUESTION_TEMPLATES)]
            if tpl:
                text = tpl.format(phrase=phrase)
                if _normalize(text) not in used or first_followup:
                    return GeneratedQuestion(
                        text=_finalize(text),
                        category="troubleshooting" if current_topic else "scenario",
                        topic=current_topic,
                        difficulty=eff_difficulty,
                        kind="cross",
                    )

    # --- 3. DISCUSSION turn (sparingly, only when we have a topic + some history). ---
    if current_topic and not behavioral_slot and questions_asked >= 2 and rng.random() < 0.15:
        tpl = _pick(_DISCUSSION_TEMPLATES, used, rng)
        if tpl:
            text = tpl.format(topic=current_topic.replace("_", "/"))
            if _normalize(text) not in used:
                return GeneratedQuestion(
                    text=_finalize(text),
                    category="casual",
                    topic=current_topic,
                    difficulty=eff_difficulty,
                    kind="discussion",
                )

    # --- 4. Behavioral / situational slots. ---
    if behavioral_slot:
        bq = _behavioral_question(round_type, eff_difficulty, used, rng)
        if bq:
            stitch = _maybe_stitch(last_answer_quality, rng)
            return GeneratedQuestion(
                text=_finalize(f"{stitch} {bq}".strip() if stitch else bq),
                category="behavioral" if round_type != "hr" else "casual",
                topic=None,
                difficulty=eff_difficulty,
                kind="behavioral",
            )

    # --- 2. TOPIC DRILL at adapted difficulty. ---
    if current_topic:
        tq = _topic_question(current_topic, eff_difficulty, used, rng)
        if tq:
            # When the candidate just gave a substantive answer on this topic,
            # frame it as "let's go deeper" so it reads as a follow-up, not a reset.
            if substantive and answer_topic == current_topic and rng.random() < 0.6:
                drill = _pick(_TOPIC_DRILL_TEMPLATES, used, rng) or "Going deeper on {topic}: {q}"
                text = drill.format(topic=current_topic.replace("_", "/"), q=tq)
                kind = "drill"
            else:
                stitch = _maybe_stitch(last_answer_quality, rng)
                text = f"{stitch} {tq}".strip() if stitch else tq
                kind = "followup" if substantive else "generated"
            if _normalize(text) not in used:
                return GeneratedQuestion(
                    text=_finalize(text),
                    category="troubleshooting",
                    topic=current_topic,
                    difficulty=eff_difficulty,
                    kind=kind,
                )

    # --- 5. Generic technical fallback — guaranteed to return something, and
    # guaranteed never to repeat a verbatim-identical question within a round. ---
    gq = _generic_question(eff_difficulty, used, rng)
    if not gq:
        # Bank exhausted: pick from a small pool of distinct open-ended prompts.
        gq = _pick(_OPEN_ENDED_FALLBACKS, used, rng)
    if not gq:
        # Even the pool is used this round: build a non-repeating variant by
        # appending a rotating "angle" suffix, keyed deterministically on how many
        # questions we've already asked (len(used)) — no Date/random calls.
        base = _OPEN_ENDED_FALLBACKS[len(used) % len(_OPEN_ENDED_FALLBACKS)]
        angle = _FALLBACK_ANGLES[len(used) % len(_FALLBACK_ANGLES)]
        gq = f"{base} {angle}"
    stitch = _maybe_stitch(last_answer_quality, rng)
    return GeneratedQuestion(
        text=_finalize(f"{stitch} {gq}".strip() if stitch else gq),
        category="technical",
        topic=current_topic,
        difficulty=eff_difficulty,
        kind="followup" if substantive else "generated",
    )


def _maybe_stitch(last_answer_quality: str, rng: random.Random) -> str:
    """Occasionally prepend a tiny acknowledgement so consecutive questions don't
    feel like a quiz. Never on a skip (the reply already handled that)."""
    if last_answer_quality in ("skipped", ""):
        return ""
    if rng.random() < 0.35:
        return rng.choice(_QUESTION_STITCHES)
    return ""
