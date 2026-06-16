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
            slug = q.pop("slug")
            _, was_created = InterviewQuestion.objects.update_or_create(slug=slug, defaults=q)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Question bank: {len(QUESTIONS)} synced ({created} new)"))
