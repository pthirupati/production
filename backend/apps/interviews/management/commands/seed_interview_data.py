"""Seed interview plan tiers, voices, platform settings, and question bank."""

from django.core.management.base import BaseCommand

from apps.interviews.models import (
    InterviewPlanTier,
    InterviewPlatformSettings,
    InterviewQuestion,
    InterviewVoiceOption,
)
from apps.interviews.services.voice_service import _default_voices


DEFAULT_TIERS = [
    {
        "code": "free",
        "name": "Free Mini Mock",
        "description": "1 text mini interview per month (15 min cap on round 1)",
        "price_inr": 0,
        "interviews_per_month": 1,
        "max_rounds": 1,
        "voice_enabled": False,
        "practical_enabled": False,
        "certificate_enabled": False,
        "order": 0,
    },
    {
        "code": "pro",
        "name": "Interview Pro",
        "description": "10 full mock interview attempts per year, voice, 3 rounds each, reports",
        "price_inr": 999,
        "interviews_per_month": 10,
        "max_rounds": 3,
        "voice_enabled": True,
        "practical_enabled": True,
        "certificate_enabled": True,
        "order": 1,
    },
    {
        "code": "premium",
        "name": "Interview Premium",
        "description": "10 interview attempts/year, up to 5 rounds each, certificate, priority scheduling",
        "price_inr": 2499,
        "interviews_per_month": 10,
        "max_rounds": 5,
        "voice_enabled": True,
        "practical_enabled": True,
        "certificate_enabled": True,
        "order": 2,
    },
]

QUESTIONS = [
    {
        "slug": "tech-linux-file-descriptors",
        "category": "technical",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["mid", "senior", "lead"],
        "technology_tags": ["linux"],
        "difficulty": 3,
        "question_text": "A production service logs 'too many open files'. Walk me through how you'd diagnose and fix it without restarting blindly.",
        "expected_keywords": ["ulimit", "lsof", "systemd", "LimitNOFILE"],
        "follow_ups": ["What if the leak is in a container?", "How would you prevent recurrence?"],
    },
    {
        "slug": "tech-k8s-crashloop",
        "category": "troubleshooting",
        "round_types": ["technical"],
        "experience_levels": ["mid", "senior"],
        "technology_tags": ["kubernetes", "docker"],
        "difficulty": 3,
        "question_text": "Pods are in CrashLoopBackOff after a deployment. What's your first ten minutes?",
        "expected_keywords": ["kubectl", "logs", "describe", "events", "rollback"],
        "follow_ups": ["How do you communicate status to stakeholders during SEV-2?"],
    },
    {
        "slug": "tech-nginx-502",
        "category": "scenario",
        "round_types": ["technical"],
        "experience_levels": ["junior", "mid", "senior"],
        "technology_tags": ["linux", "nginx"],
        "difficulty": 2,
        "question_text": "Users report 502 from nginx reverse proxy. Backend app is 'healthy' per health check. What do you check?",
        "expected_keywords": ["upstream", "timeout", "proxy", "socket", "logs"],
    },
    {
        "slug": "practical-sshd-down",
        "category": "practical",
        "round_types": ["technical"],
        "experience_levels": ["junior", "mid", "senior"],
        "technology_tags": ["linux"],
        "difficulty": 2,
        "question_text": "Hands-on: SSH to the server is failing. On the server console, diagnose and restore remote access.",
        "expected_keywords": ["sshd", "systemctl", "port 22", "firewall"],
        "practical_config": {
            "setup": "Use the terminal panel. Run: systemctl status sshd — then fix the service.",
            "scenario_slug": "sim-rhel-ssh-stop",
            "validate_commands": ["systemctl start sshd", "systemctl restart sshd"],
        },
    },
    {
        "slug": "mgr-sev1-process",
        "category": "itil",
        "round_types": ["manager"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "Walk me through how you run a SEV-1 incident bridge — roles, comms cadence, and when you'd escalate to leadership.",
        "expected_keywords": ["incident commander", "timeline", "postmortem", "stakeholder"],
    },
    {
        "slug": "mgr-sla-breach",
        "category": "sla",
        "round_types": ["manager"],
        "experience_levels": ["senior", "lead"],
        "difficulty": 4,
        "question_text": "Monthly uptime SLA is 99.9% but you're trending toward breach on day 20. What actions do you take?",
        "expected_keywords": ["error budget", "change freeze", "risk", "communication"],
    },
    {
        "slug": "hr-background",
        "category": "casual",
        "round_types": ["hr"],
        "experience_levels": ["junior", "mid", "senior", "lead"],
        "difficulty": 1,
        "question_text": "Tell me about yourself — but keep it under two minutes and tie it to why this role.",
        "expected_keywords": [],
    },
    {
        "slug": "hr-notice-ctc",
        "category": "behavioral",
        "round_types": ["hr"],
        "experience_levels": ["mid", "senior"],
        "difficulty": 2,
        "question_text": "What's your notice period, and what compensation range would make this move a yes for you?",
        "expected_keywords": ["notice", "expectation"],
    },
    {
        "slug": "tricky-dns-split-brain",
        "category": "tricky",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["senior", "lead"],
        "technology_tags": ["networking"],
        "difficulty": 5,
        "question_text": "Half your users resolve the API to an old IP after a migration. DNS TTL was 300. What happened and how do you prove it?",
        "expected_keywords": ["TTL", "cache", "dig", "resolver"],
    },
    {
        "slug": "tech-docker-image-pull",
        "category": "technical",
        "round_types": ["technical"],
        "experience_levels": ["mid", "senior"],
        "technology_tags": ["docker"],
        "difficulty": 2,
        "question_text": "CI builds pass but deploy fails with ImagePullBackOff. How do you troubleshoot?",
        "expected_keywords": ["registry", "credentials", "tag", "imagePullSecrets"],
    },
    {
        "slug": "lead-influence-deadline",
        "category": "behavioral",
        "round_types": ["leadership", "manager"],
        "experience_levels": ["senior", "lead"],
        "difficulty": 4,
        "question_text": "Product wants a Friday release; you believe rollback risk is too high. How do you push back without damaging the relationship?",
        "expected_keywords": ["data", "risk", "alternative", "stakeholder"],
    },
    {
        "slug": "tech-db-replication-lag",
        "category": "technical",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["senior"],
        "technology_tags": ["mysql", "postgres"],
        "difficulty": 4,
        "question_text": "Read replicas are 30 minutes behind. What metrics and queries do you use to find root cause?",
        "expected_keywords": ["replication", "lag", "binlog", "slow query"],
    },
]


# ---------------------------------------------------------------------------
# P2.9 — ITIL / SLA + tougher/trickier content, grouped by the round type the
# adaptive engine pulls them for. All rule-based, no paid APIs.
#
#   * manager (techno-managerial) → incident/change/problem mgmt, SLA/SLO/MTTR,
#     escalation, prioritization, stakeholder comms, leadership trade-offs.
#   * hr → behavioral + casual + HR logistics (motivation, culture, conflict,
#     failure, compensation) scored on STAR coverage.
#   * technical / deep_dive → harder scenario-based troubleshooting, trick
#     questions, and hands-on practical tasks wired to real scenario slugs +
#     accepted-command patterns so the inline validator (P2.4) can grade them.
# ---------------------------------------------------------------------------

ITIL_SLA_PROCESS_QUESTIONS = [
    {
        "slug": "itil-incident-vs-problem",
        "category": "itil",
        "round_types": ["manager", "leadership"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "In ITIL terms, what's the difference between incident management and problem management, and how do you make sure problems actually get worked after the fire is out?",
        "expected_keywords": ["incident", "problem", "root cause", "known error", "backlog"],
        "follow_ups": [
            "Who owns the problem record once the incident is resolved?",
            "How do you stop the same incident recurring every month?",
        ],
        "discussion_prompts": ["known error database", "blameless culture"],
    },
    {
        "slug": "itil-change-management-cab",
        "category": "itil",
        "round_types": ["manager"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "Walk me through your change management process — standard vs normal vs emergency change, and where the CAB fits. How do you keep it from becoming a bureaucratic bottleneck?",
        "expected_keywords": ["change", "CAB", "emergency", "rollback", "approval", "risk"],
        "follow_ups": ["What goes in a change record?", "How do you handle a failed change at 2 AM?"],
    },
    {
        "slug": "itil-emergency-change",
        "category": "itil",
        "round_types": ["manager", "leadership"],
        "experience_levels": ["senior", "lead"],
        "difficulty": 4,
        "question_text": "A SEV-1 needs a config change RIGHT NOW but your process requires CAB approval. What do you do, and how do you reconcile it with the change process afterward?",
        "expected_keywords": ["emergency change", "ECAB", "retroactive", "approval", "documentation"],
    },
    {
        "slug": "sla-slo-sli-difference",
        "category": "sla",
        "round_types": ["manager", "technical"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "Explain SLA vs SLO vs SLI with a concrete example. If your SLA is 99.9% but the SLO is 99.95%, why would you set them differently?",
        "expected_keywords": ["SLA", "SLO", "SLI", "error budget", "buffer", "penalty"],
        "follow_ups": ["What's an error budget and how do you spend it?"],
    },
    {
        "slug": "sla-mttr-mtbf-metrics",
        "category": "sla",
        "round_types": ["manager"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "Leadership wants to reduce MTTR by 40% this quarter. What does MTTR actually measure, and what concrete levers would you pull to move it?",
        "expected_keywords": ["MTTR", "detection", "alerting", "runbook", "automation", "rollback"],
        "discussion_prompts": ["mean time to detect", "mean time to acknowledge"],
    },
    {
        "slug": "sla-error-budget-burn",
        "category": "sla",
        "round_types": ["manager", "leadership"],
        "experience_levels": ["senior", "lead"],
        "difficulty": 4,
        "question_text": "You've burned 90% of your monthly error budget by day 12. Product wants to ship a risky feature. How do you handle that conversation and decision?",
        "expected_keywords": ["error budget", "freeze", "risk", "stakeholder", "reliability", "trade-off"],
    },
    {
        "slug": "mgr-sev1-comms-cadence",
        "category": "sla",
        "round_types": ["manager", "leadership"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "During a major outage, how do you structure stakeholder communication — cadence, audience, and what you say when you DON'T yet know the root cause?",
        "expected_keywords": ["incident commander", "status", "cadence", "stakeholder", "ETA", "transparency"],
        "follow_ups": ["How is the message to execs different from the one to engineers?"],
    },
    {
        "slug": "mgr-prioritize-multiple-p1",
        "category": "scenario",
        "round_types": ["manager", "leadership"],
        "experience_levels": ["senior", "lead"],
        "difficulty": 4,
        "question_text": "Three P1s land at once: a payment outage, a data-export breach risk, and a noisy-but-harmless alert storm. Limited on-call staff. How do you triage and delegate?",
        "expected_keywords": ["severity", "impact", "delegate", "incident commander", "triage", "comms"],
    },
    {
        "slug": "mgr-postmortem-blameless",
        "category": "itil",
        "round_types": ["manager", "leadership"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "An engineer's change caused a 2-hour outage. Walk me through how you run the postmortem so it's blameless but the action items actually land.",
        "expected_keywords": ["blameless", "timeline", "contributing factors", "action items", "owner", "follow-up"],
    },
    {
        "slug": "mgr-oncall-burnout",
        "category": "behavioral",
        "round_types": ["manager", "leadership"],
        "experience_levels": ["senior", "lead"],
        "difficulty": 3,
        "question_text": "Your on-call rotation is burning people out — pages every night, attrition rising. As the manager, what do you change in the next 30/60/90 days?",
        "expected_keywords": ["alert", "rotation", "toil", "automation", "staffing", "retro"],
    },
]

HR_BEHAVIORAL_QUESTIONS = [
    {
        "slug": "hr-why-leaving",
        "category": "casual",
        "round_types": ["hr"],
        "experience_levels": ["junior", "mid", "senior", "lead"],
        "difficulty": 1,
        "question_text": "What's prompting you to look for a new role right now, and what would make this one a clear step up for you?",
        "expected_keywords": [],
        "discussion_prompts": ["growth", "scope", "compensation", "culture"],
    },
    {
        "slug": "hr-conflict-coworker",
        "category": "behavioral",
        "round_types": ["hr"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "Tell me about a time you strongly disagreed with a teammate on a technical decision. How did it play out?",
        "expected_keywords": ["situation", "disagreement", "data", "resolution", "outcome"],
        "follow_ups": ["Looking back, would you handle it differently?"],
    },
    {
        "slug": "hr-biggest-failure",
        "category": "behavioral",
        "round_types": ["hr"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "Describe a project that failed or missed its goal. What was your role, and what did you actually change afterward?",
        "expected_keywords": ["responsible", "mistake", "learned", "changed", "outcome"],
    },
    {
        "slug": "hr-handle-ambiguity",
        "category": "behavioral",
        "round_types": ["hr", "manager"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 3,
        "question_text": "Tell me about a time you had to deliver something with unclear or shifting requirements. How did you make progress?",
        "expected_keywords": ["ambiguity", "clarify", "assumptions", "stakeholder", "iterate", "result"],
    },
    {
        "slug": "hr-feedback-receiving",
        "category": "behavioral",
        "round_types": ["hr"],
        "experience_levels": ["junior", "mid", "senior"],
        "difficulty": 2,
        "question_text": "Tell me about a piece of critical feedback you received that stung at first. What did you do with it?",
        "expected_keywords": ["feedback", "reaction", "reflected", "changed", "improved"],
    },
    {
        "slug": "hr-culture-fit",
        "category": "casual",
        "round_types": ["hr"],
        "experience_levels": ["junior", "mid", "senior", "lead"],
        "difficulty": 1,
        "question_text": "What kind of team environment brings out your best work — and what kind drains you?",
        "expected_keywords": [],
    },
    {
        "slug": "hr-comp-expectations",
        "category": "behavioral",
        "round_types": ["hr"],
        "experience_levels": ["mid", "senior", "lead"],
        "difficulty": 2,
        "question_text": "What are your compensation expectations, and how flexible are you across base, bonus, and equity? Walk me through your thinking.",
        "expected_keywords": ["range", "base", "total", "flexible", "market"],
    },
    {
        "slug": "hr-relocation-remote",
        "category": "casual",
        "round_types": ["hr"],
        "experience_levels": ["junior", "mid", "senior", "lead"],
        "difficulty": 1,
        "question_text": "How do you feel about hybrid/on-site versus fully remote, and are there any constraints we should know about up front?",
        "expected_keywords": [],
    },
]

HARD_TECHNICAL_QUESTIONS = [
    {
        "slug": "tricky-it-works-on-my-machine",
        "category": "tricky",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["mid", "senior", "lead"],
        "technology_tags": ["docker", "linux"],
        "difficulty": 4,
        "question_text": "A build passes locally and in CI but the container crashes only in production. Nothing in the logs. How do you reason about what's different, and where do you look first?",
        "expected_keywords": ["environment", "resource limits", "config", "secrets", "readiness", "OOM"],
        "follow_ups": ["What if it only happens under real traffic?"],
    },
    {
        "slug": "tricky-load-high-cpu-low",
        "category": "tricky",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["mid", "senior", "lead"],
        "technology_tags": ["linux"],
        "difficulty": 5,
        "question_text": "Load average is 60 on an 8-core box but CPU utilization sits at 10%. Users say the app is slow. What's your hypothesis and how do you confirm it?",
        "expected_keywords": ["uninterruptible", "D state", "io wait", "blocked", "disk", "iostat"],
    },
    {
        "slug": "tricky-dns-ttl-stale",
        "category": "tricky",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["senior", "lead"],
        "technology_tags": ["networking"],
        "difficulty": 5,
        "question_text": "After a failover you flipped DNS, but half your traffic still hits the dead host an hour later despite a 60s TTL. Why might that be, and how do you prove where the stale cache lives?",
        "expected_keywords": ["TTL", "resolver", "negative cache", "client cache", "dig", "connection reuse"],
    },
    {
        "slug": "scenario-k8s-oomkilled-intermittent",
        "category": "scenario",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["mid", "senior"],
        "technology_tags": ["kubernetes"],
        "difficulty": 4,
        "question_text": "A pod restarts a few times an hour with OOMKilled, but memory looks fine in your dashboards most of the time. How do you catch the spike and decide between a limit bump and a real leak?",
        "expected_keywords": ["limits", "requests", "OOMKilled", "describe", "metrics", "heap", "leak"],
        "follow_ups": ["What's the risk of just raising the memory limit?"],
    },
    {
        "slug": "scenario-tls-cert-expiry",
        "category": "scenario",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["mid", "senior"],
        "technology_tags": ["linux", "nginx", "security"],
        "difficulty": 3,
        "question_text": "Customers report TLS errors starting at midnight. curl works from one box but not another. How do you confirm it's an expired/!chained cert and prevent the 3 AM page next time?",
        "expected_keywords": ["openssl", "expiry", "chain", "intermediate", "monitoring", "renewal"],
    },
    {
        "slug": "scenario-terraform-state-drift",
        "category": "scenario",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["senior", "lead"],
        "technology_tags": ["terraform", "aws"],
        "difficulty": 4,
        "question_text": "Someone changed infrastructure in the AWS console and now `terraform plan` wants to destroy and recreate a production database. How do you recover safely without data loss?",
        "expected_keywords": ["drift", "import", "state", "lifecycle", "prevent_destroy", "backup"],
    },
    {
        "slug": "tech-systemdesign-rate-limit",
        "category": "system_design",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["senior", "lead"],
        "difficulty": 4,
        "question_text": "Design a rate limiter for a public API serving 50k req/s across many nodes. Walk me through the algorithm, where state lives, and the failure modes.",
        "expected_keywords": ["token bucket", "sliding window", "redis", "distributed", "burst", "fail open"],
        "follow_ups": ["What happens when your Redis is down — fail open or closed?"],
    },
    # ── Hands-on practical tasks wired to real scenarios + accepted commands ──
    # The inline validator (P2.4) grades these against the labs simulation OR the
    # accepted-command patterns below, then awards the practical (+15) credit.
    {
        "slug": "practical-nginx-down",
        "category": "practical",
        "round_types": ["technical"],
        "experience_levels": ["junior", "mid", "senior"],
        "technology_tags": ["linux", "nginx"],
        "difficulty": 2,
        "question_text": "Hands-on: nginx won't start after a config edit. Diagnose why and restore HTTP 200, then tell me the command that pointed you at the problem.",
        "expected_keywords": ["nginx -t", "systemctl", "journalctl", "reload"],
        "practical_config": {
            "setup": "Use the lab terminal, or type the command(s) here and I'll check them. Start by validating the config.",
            "scenario_slug": "sim-rhel-nginx-down",
            "expected_commands": [
                r"nginx\s+-t",
                r"systemctl\s+(restart|start|reload)\s+nginx",
            ],
        },
    },
    {
        "slug": "practical-firewall-port-80",
        "category": "practical",
        "round_types": ["technical"],
        "experience_levels": ["mid", "senior"],
        "technology_tags": ["linux", "security"],
        "difficulty": 3,
        "question_text": "Hands-on: the web app is up but unreachable from outside. You suspect the firewall. What command opens port 80/tcp persistently on a RHEL box?",
        "expected_keywords": ["firewall-cmd", "permanent", "reload", "80/tcp"],
        "practical_config": {
            "setup": "Type the firewalld command(s) you'd run. Remember to make it persist a reload.",
            "scenario_slug": "sim-rhel-firewall-block",
            "expected_commands": [
                r"firewall-cmd\s+.*--add-port[= ]80/tcp.*--permanent|firewall-cmd\s+.*--permanent.*--add-port[= ]80/tcp",
                r"firewall-cmd\s+--reload",
            ],
        },
    },
    {
        "slug": "practical-py-fizzbuzz",
        "category": "practical",
        "round_types": ["technical", "deep_dive"],
        "experience_levels": ["junior", "mid"],
        "technology_tags": ["python"],
        "difficulty": 2,
        "question_text": "Quick code task: write a Python function `classify(n)` that returns 'fizz' for multiples of 3, 'buzz' for multiples of 5, 'fizzbuzz' for both, and the number as a string otherwise.",
        "expected_keywords": ["def", "return", "%", "fizz", "buzz"],
        "practical_config": {
            "setup": "Type your Python function in the box and I'll run it against hidden tests.",
            "code": {
                "language": "python",
                "tests": [
                    {"name": "fizz", "code": "assert classify(3) == 'fizz'"},
                    {"name": "buzz", "code": "assert classify(5) == 'buzz'"},
                    {"name": "fizzbuzz", "code": "assert classify(15) == 'fizzbuzz'", "hidden": True},
                    {"name": "plain", "code": "assert classify(7) == '7'", "hidden": True},
                ],
            },
        },
    },
]


# Combine the new content into the seeded bank.
QUESTIONS = QUESTIONS + ITIL_SLA_PROCESS_QUESTIONS + HR_BEHAVIORAL_QUESTIONS + HARD_TECHNICAL_QUESTIONS


class Command(BaseCommand):
    help = "Seed interview plan tiers and question bank"

    def handle(self, *args, **options):
        for t in DEFAULT_TIERS:
            InterviewPlanTier.objects.update_or_create(code=t["code"], defaults=t)
        self.stdout.write(self.style.SUCCESS(f"Synced {len(DEFAULT_TIERS)} plan tiers"))

        settings_row, created = InterviewPlatformSettings.objects.get_or_create(pk=1)
        if created:
            settings_row.enabled = True
            settings_row.staff_free_by_default = True
            settings_row.voice_engine = "browser"
            settings_row.save()
        self.stdout.write(self.style.SUCCESS("Platform settings ready (pk=1)"))

        for i, v in enumerate(_default_voices()):
            InterviewVoiceOption.objects.update_or_create(
                code=v["code"],
                defaults={
                    "label": v["label"],
                    "locale": v["locale"],
                    "gender": v["gender"],
                    "region": v["region"],
                    "browser_voice_hint": v["browser_voice_hint"],
                    "pitch": v["pitch"],
                    "rate": v["rate"],
                    "is_default": v["is_default"],
                    "is_active": True,
                    "order": i,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Synced {len(_default_voices())} browser voices"))

        created = 0
        for q in QUESTIONS:
            # Copy so we never mutate the module-level dicts (the command can run
            # more than once in a single process, e.g. across tests).
            data = dict(q)
            slug = data.pop("slug")
            _, was_created = InterviewQuestion.objects.update_or_create(slug=slug, defaults=data)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Question bank: {len(QUESTIONS)} synced ({created} new)"))
