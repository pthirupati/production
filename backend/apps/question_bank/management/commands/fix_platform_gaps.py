"""One-shot platform gap fixes: prompt labs, devops lab_mode, AWS tracks metadata.

Run: python manage.py fix_platform_gaps
"""

from __future__ import annotations

import glob
import os
import re

import yaml
from django.core.management.base import BaseCommand

SCENARIOS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "scenarios")

# Map academy prompt slug topic token → exercise rubric
PROMPT_TOPIC_EXERCISES = {
    "instructions": ("write-instructions", "Write clear instructions", "Draft a prompt with role, task, and output format.", {"require_any_role": True, "min_words": 15, "mentions_limit": True}),
    "context": ("add-context", "Add context", "Write a prompt that includes background context and a specific task.", {"require_any_role": True, "min_words": 20, "has_delimiter": True}),
    "examples": ("few-shot", "Use examples", "Write a few-shot prompt with at least one input→output example.", {"min_example_pairs": 1, "min_words": 25}),
    "evaluation": ("eval-criteria", "Define evaluation criteria", "Write a prompt that states how outputs should be judged.", {"mentions_limit": True, "min_words": 18, "require_any_role": True}),
    "tools": ("tool-use", "Tool-use prompt", "Write a prompt that asks the model to use tools step by step.", {"min_words": 20, "require_any_role": True}),
    "structured": ("structured-output", "Structured output", "Ask for JSON output with explicit schema constraints.", {"requires_json_request": True, "min_words": 15}),
    "safety": ("safety-guardrails", "Safety guardrails", "Write a prompt with constraints on what to avoid.", {"mentions_limit": True, "min_words": 18}),
    "agents": ("agent-loop", "Agent instructions", "Write a multi-step agent prompt with clear stop conditions.", {"min_words": 25, "require_any_role": True}),
    "debugging": ("debug-prompt", "Debug a prompt", "Rewrite a vague prompt to be specific and contradiction-free.", {"no_contradiction": True, "min_words": 20, "require_any_role": True}),
    "templates": ("reusable-template", "Reusable template", "Create a template prompt with placeholders for context.", {"has_delimiter": True, "min_words": 20}),
}

DEFAULT_EXERCISE = ("practice-prompt", "Practice prompt", "Write a specific, well-scoped prompt for this lesson topic.", {"require_any_role": True, "min_words": 15, "mentions_limit": True})

AWS_TRACKS = [
    ("fundamentals", ["learn-iam", "learn-vpc", "learn-ec2", "learn-s3", "build-iam", "build-vpc", "build-ec2", "build-s3"]),
    ("compute-storage", ["learn-ebs", "learn-efs", "build-ebs", "build-efs", "operate-elb", "troubleshoot-ebs"]),
    ("networking", ["learn-elb", "operate-elb", "troubleshoot-vpc", "production-nat", "integration-route53", "security-vpc-peering"]),
    ("security", ["security-groups", "security-rds", "security-kms", "security-waf", "security-guardduty", "security-cognito"]),
    ("serverless-data", ["learn-lambda", "learn-rds", "learn-dynamodb", "operate-lambda", "operate-rds", "integration-dynamodb"]),
    ("containers", ["learn-eks", "learn-ecr", "build-eks", "operate-eks", "troubleshoot-eks", "integration-ecs"]),
    ("iac", ["automation-lambda", "automation-terraform", "operate-cloudformation", "production-ssm"]),
    ("troubleshooting", ["troubleshoot-vpc", "troubleshoot-nlb", "troubleshoot-config", "troubleshoot-rds", "observability-cloudwatch", "backup-autoscaling"]),
]


def _topic_from_slug(slug: str) -> str:
    parts = slug.split("-")
    for p in reversed(parts):
        if p in PROMPT_TOPIC_EXERCISES or p.rstrip("0123456789") in PROMPT_TOPIC_EXERCISES:
            base = p.rstrip("0123456789")
            return base if base in PROMPT_TOPIC_EXERCISES else p
    return "instructions"


def _prompt_coding_spec(title: str, topic: str, objectives: list) -> dict:
    ex_id, ex_title, ex_goal, success = PROMPT_TOPIC_EXERCISES.get(topic, DEFAULT_EXERCISE)
    topic_label = topic.replace("-", " ").title()
    return {
        "kind": "prompt",
        "language": "text",
        "prompt_config": {
            "persona": "A helpful AI assistant for learning prompt engineering.",
            "lesson": [
                {"heading": f"About {topic_label}", "body": f"This lab teaches {topic_label.lower()} — one of the core skills for reliable LLM workflows. Use the practice console to draft and score your prompt against the rubric."},
                {"heading": "What good looks like", "body": "Strong prompts assign a role, state the task clearly, set constraints (length, tone, format), and specify the output shape. Vague prompts score low; specific prompts score 80+."},
            ],
            "rubric": ["role", "context", "task", "constraints", "format", "specificity"],
            "exercises": [
                {
                    "id": ex_id,
                    "title": ex_title,
                    "goal": ex_goal,
                    "success": success,
                    "starter": "Write your prompt here…",
                }
            ],
        },
        "instructions": f"Complete the {title} exercise in the Prompt Playground. Score 80+ on the rubric, then submit.",
    }


class Command(BaseCommand):
    help = "Fix P0–P1 platform gaps in scenario YAML (prompt labs, devops lab_mode, AWS tracks)."

    def handle(self, *args, **options):
        prompt_fixed = self._fix_academy_prompt_labs()
        devops_fixed = self._fix_devops_lab_mode()
        aws_tagged = self._tag_aws_tracks()
        self._strip_prompt_nginx_e2e_map()
        self.stdout.write(self.style.SUCCESS(
            f"Done: {prompt_fixed} prompt labs → PromptPlayground, "
            f"{devops_fixed} devops lab_mode set, {aws_tagged} AWS track tags"
        ))

    def _fix_academy_prompt_labs(self) -> int:
        count = 0
        for path in glob.glob(os.path.join(SCENARIOS, "prompt-engineering", "academy-prompt-engineering-*", "scenario.yaml")):
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            if data.get("coding_mode"):
                continue
            slug = data.get("slug") or ""
            title = (data.get("title") or "Prompt Lab").replace(" — Learn Lab", "").replace(" — Build Lab", "")
            topic = _topic_from_slug(slug)
            data["coding_mode"] = True
            data["lab_mode"] = "simulation"
            data["simulation_type"] = "generic"
            data.pop("infrastructure_type", None)
            data["coding_spec"] = _prompt_coding_spec(title, topic, data.get("objectives") or [])
            # Clean nginx-centric objectives/hints/tasks
            objs = data.get("objectives") or []
            data["objectives"] = [o for o in objs if "nginx" not in o.lower() and "systemctl" not in o.lower()] or [
                f"Write a strong prompt for {topic.replace('-', ' ')}",
                "Score 80+ on the practice console rubric",
                "Submit when all exercises pass",
            ]
            data["initial_state"] = (
                "A guided AI practice console opens in your browser. "
                "It is a rule-based simulator (no real model, no API cost) that scores your prompt live."
            )
            data["hints"] = [
                {"order": 1, "cost": 0, "content": "Include WHO the AI should act as (role), WHAT to do (task), and HOW to format the answer."},
                {"order": 2, "cost": 25, "content": "Add constraints: word count, audience, tone, or things to avoid."},
                {"order": 3, "cost": 50, "content": "Use the live score panel — aim for 80+ before submitting."},
            ]
            data["tasks"] = [{
                "id": "task_1",
                "title": title,
                "description": f"Complete the {topic.replace('-', ' ')} prompt exercise in the practice console.",
                "validation": {"type": "custom_script", "script": "hidden_tests", "error_message": "Prompt did not meet the rubric. Revise and submit again."},
            }]
            data["guided_mode"] = {
                "enabled": True,
                "steps": [
                    {"step": 1, "title": "Read the lesson", "instruction": "Review the lesson panels in the Prompt Playground.", "command": "open playground", "expected_output": "Lesson content visible", "explanation": "Understand the rubric before writing.", "next_on": "manual"},
                    {"step": 2, "title": "Draft your prompt", "instruction": "Write your prompt in the editor and check the live score.", "command": "draft prompt", "expected_output": "Score 80+ on rubric", "explanation": "Iterate until specific enough.", "next_on": "manual"},
                    {"step": 3, "title": "Submit for grading", "instruction": "Submit when all exercises pass.", "command": "submit", "expected_output": "All exercises passed", "explanation": "Server re-checks your prompt.", "next_on": "validate"},
                ],
            }
            data["solution"] = {
                "summary": f"Write a specific prompt covering role, task, constraints, and format for {topic}.",
                "files_changed": [],
                "commands_run": [],
            }
            if "nginx" in (data.get("description") or ""):
                data["description"] = re.sub(
                    r"Success means.*?systemctl is-active nginx.*?\.",
                    "Success means all prompt exercises pass the rubric.",
                    data["description"],
                    flags=re.DOTALL,
                )
            with open(path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            count += 1
        return count

    def _fix_devops_lab_mode(self) -> int:
        missing_slugs = {
            "kubernetes-pod-crashloop", "alertmanager-silence", "argocd-sync-failed",
            "consul-service-deregister", "helm-rollback-needed", "fluentd-buffer-overflow",
            "jenkins-job-oom", "cicd-pipeline-broken", "terraform-state-lock",
            "terraform-apply-failed", "helm-chart-failed", "nginx-upstream-health",
            "github-actions-secret-missing", "sonarqube-quality-gate", "vault-sealed",
            "elk-logstash-parsing", "nexus-artifact-upload", "istio-sidecar-inject",
            "gitlab-ci-runner-stuck", "postgres-refused", "prometheus-scrape-failing",
            "ansible-vault-decrypt", "haproxy-backend-down", "packer-build-timeout",
            "grafana-dashboard-no-data", "jenkins-pipeline-fail", "docker-registry-push-fail",
            "terraform-drift-detected",
        }
        count = 0
        for slug in missing_slugs:
            matches = glob.glob(os.path.join(SCENARIOS, "devops", slug, "scenario.yaml"))
            if not matches:
                matches = glob.glob(os.path.join(SCENARIOS, "*", slug, "scenario.yaml"))
            for path in matches:
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                if data.get("lab_mode"):
                    continue
                data["lab_mode"] = "simulation"
                data.setdefault("simulation_type", "devops")
                with open(path, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                count += 1
        return count

    def _tag_aws_tracks(self) -> int:
        count = 0
        for track_name, keywords in AWS_TRACKS:
            for path in glob.glob(os.path.join(SCENARIOS, "aws", "academy-aws-*", "scenario.yaml")):
                slug = os.path.basename(os.path.dirname(path))
                if not any(k in slug for k in keywords):
                    continue
                with open(path) as f:
                    data = yaml.safe_load(f) or {}
                tags = list(data.get("tags") or [])
                tag = f"aws-track:{track_name}"
                if tag not in tags:
                    tags.append(tag)
                    data["tags"] = tags
                    data["learning_track"] = track_name
                    with open(path, "w") as f:
                        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                    count += 1
        return count

    def _strip_prompt_nginx_e2e_map(self) -> None:
        path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..",
            "apps", "labs", "provisioner", "simulation", "academy_service_e2e_fixes.py",
        ))
        if not os.path.exists(path):
            return
        with open(path) as f:
            text = f.read()
        new_lines = []
        for line in text.splitlines():
            if "academy-prompt-engineering-" in line and "'nginx'" in line:
                continue
            new_lines.append(line)
        with open(path, "w") as f:
            f.write("\n".join(new_lines) + "\n")
