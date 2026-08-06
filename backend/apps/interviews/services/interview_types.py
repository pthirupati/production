"""
Extended interview type definitions.

Each type defines:
  - persona defaults
  - system prompt addendum
  - question category weights
  - evaluation criteria weights
  - special evaluation hooks

Extended types (opt-in, not in InterviewRound.ROUND_TYPES):
  behavioral   — STAR method evaluation
  system_design — architecture + diagramming
  live_coding   — code review + execution prompts
  devops_debug  — Kubernetes/infra incident scenarios
  sre_oncall    — SRE on-call runbook scenarios

Core types — these are the values InterviewRound.round_type actually stores
(models.InterviewRound.ROUND_TYPES): technical, manager, hr, deep_dive,
leadership. They previously had no entry here at all, so every real round in
the database fell through get_eval_weights() to the technical defaults — an HR
round was scored with 35% technical weight. Each now carries weights that match
what the round is actually probing.
"""

from __future__ import annotations

INTERVIEW_TYPE_CONFIGS: dict[str, dict] = {
    "behavioral": {
        "persona_addendum": (
            "You are evaluating behavioral competencies. For every answer, "
            "mentally check: did they describe a Situation, Task, Action, Result? "
            "If any component is missing, gently prompt for it: "
            "'What was the outcome?' or 'What was your specific role?' "
            "Never explicitly say 'STAR method' to the candidate."
        ),
        "question_weights": {
            "leadership": 0.35,
            "conflict_resolution": 0.25,
            "collaboration": 0.20,
            "failure_handling": 0.20,
        },
        "eval_weights": {
            "communication_score": 0.40,
            "problem_solving_score": 0.30,
            "technical_score": 0.10,
            "presence_score": 0.20,
        },
        "hooks": ["evaluate_star_response"],
    },

    "system_design": {
        "persona_addendum": (
            "You are running a system design interview. Start with a broad open-ended prompt. "
            "Then progressively drill: capacity estimates, API design, database choice, "
            "caching strategy, failure modes, scaling beyond single-region. "
            "Ask the candidate to narrate their diagram as they draw. "
            "Probe trade-offs — SQL vs NoSQL, sync vs async, consistency vs availability."
        ),
        "opening_prompts": [
            "Design a URL shortener that handles 1 billion URLs and 100K reads/second.",
            "Design a distributed job scheduler for a cloud platform.",
            "Design the monitoring stack for a 500-node Kubernetes cluster.",
            "Design a notification service that sends 10 million push notifications per hour.",
        ],
        "question_weights": {
            "architecture": 0.35,
            "scalability": 0.25,
            "reliability": 0.25,
            "api_design": 0.15,
        },
        "eval_weights": {
            "technical_score": 0.45,
            "problem_solving_score": 0.35,
            "communication_score": 0.20,
        },
        "hooks": [],
    },

    "live_coding": {
        "persona_addendum": (
            "You are running a live coding interview. Present a realistic DevOps/SRE problem. "
            "Ask the candidate to share their screen and write code live (or paste code into the answer). "
            "Evaluate: does the code actually work? Is it readable? Are edge cases handled? "
            "Good prompts: write a Prometheus exporter, debug this Python snippet, "
            "write a Kubernetes health-check sidecar, fix this Ansible playbook. "
            "Ask 'what would break if input X was empty?' after they submit."
        ),
        "starter_problems": [
            {
                "title": "Prometheus exporter",
                "prompt": (
                    "Write a Python Prometheus exporter that exposes a gauge `disk_free_bytes` "
                    "for each mounted filesystem. Use the `prometheus_client` library. "
                    "It should serve on port 9100 and update every 30 seconds."
                ),
                "expected_signals": ["prometheus_client", "Gauge", "start_http_server", "os.statvfs"],
            },
            {
                "title": "K8s health sidecar",
                "prompt": (
                    "Write a Go or Python HTTP server that acts as a Kubernetes readiness probe. "
                    "It should check if a file `/tmp/ready` exists and return 200 if so, 503 otherwise. "
                    "The file is written by the main container when it's ready."
                ),
                "expected_signals": ["HTTP server", "file check", "200/503 status"],
            },
            {
                "title": "Log parser",
                "prompt": (
                    "Write a Python script that reads nginx access logs from stdin, "
                    "counts requests per status code, and prints a summary table. "
                    "Handle malformed lines gracefully."
                ),
                "expected_signals": ["stdin", "regex or split", "Counter or dict", "try/except"],
            },
        ],
        "eval_weights": {
            "technical_score": 0.50,
            "practical_score": 0.30,
            "problem_solving_score": 0.20,
        },
        "hooks": [],
    },

    "devops_debug": {
        "persona_addendum": (
            "You are a senior SRE running a scenario-based debug interview. "
            "Present a realistic incident: a service is down, metrics are spiking, pods are crashing. "
            "Give clues one at a time as the candidate asks questions or runs commands. "
            "Evaluate their methodology: do they check logs first? Do they isolate the blast radius? "
            "Do they communicate while debugging? Do they think about rollback?"
        ),
        "scenarios": [
            {
                "title": "OOMKilled pods",
                "setup": (
                    "Alertmanager fires: 40% of payment-service pods are OOMKilled. "
                    "CPU is normal. Memory limit is 512Mi. Recent deploy: added a new cache layer."
                ),
                "clues": {
                    "kubectl describe pod": "OOMKilled, last exit 137",
                    "kubectl top pod": "memory at 490Mi before kill",
                    "git log": "cache TTL was changed from 60s to 3600s in latest commit",
                },
                "root_cause": "Cache TTL increase caused unbounded memory growth",
                "expected_fix": "Rollback deploy, or add cache size limit, or reduce TTL",
            },
            {
                "title": "CrashLoopBackOff",
                "setup": (
                    "New deployment: api-gateway pods immediately go CrashLoopBackOff. "
                    "Previous version ran fine. ConfigMap was updated 10 minutes ago."
                ),
                "clues": {
                    "kubectl logs": "panic: runtime error: invalid memory address (nil pointer)",
                    "kubectl get configmap": "DB_HOST was changed from 'postgres' to 'postgres.svc.cluster.local'",
                    "psql connect test": "DNS resolution fails — wrong namespace in FQDN",
                },
                "root_cause": "ConfigMap DNS name wrong — missing namespace",
                "expected_fix": "Fix FQDN to postgres.default.svc.cluster.local",
            },
        ],
        "eval_weights": {
            "technical_score": 0.40,
            "problem_solving_score": 0.40,
            "communication_score": 0.20,
        },
        "hooks": [],
    },

    "sre_oncall": {
        "persona_addendum": (
            "You are simulating an SRE on-call scenario. The candidate is now the on-call engineer. "
            "An alert just fired. Walk them through the incident. Evaluate: "
            "do they establish severity first? Do they check dashboards before making changes? "
            "Do they communicate to stakeholders? Do they write an incident timeline? "
            "Do they suggest a blameless postmortem?"
        ),
        "eval_weights": {
            "technical_score": 0.30,
            "problem_solving_score": 0.35,
            "communication_score": 0.35,
        },
        "hooks": [],
    },

    # --- Core round types (InterviewRound.ROUND_TYPES) ---
    # scoring.aggregate_round_scores only computes a real practical_score for
    # technical/live_coding/devops_debug/sre_oncall rounds; for every other type
    # it silently falls back to the raw answer average. So practical_score is
    # only given weight on the round types that actually produce one.

    "technical": {
        "eval_weights": {
            "technical_score": 0.35,
            "communication_score": 0.20,
            "problem_solving_score": 0.25,
            "practical_score": 0.20,
        },
        "hooks": [],
    },

    "manager": {
        # Techno-manager: process, ownership and stakeholder handling carry the
        # round; technical depth still matters but is no longer the top weight.
        "eval_weights": {
            "communication_score": 0.35,
            "problem_solving_score": 0.30,
            "technical_score": 0.20,
            "presence_score": 0.15,
        },
        "hooks": [],
    },

    "hr": {
        # HR screens motivation, career narrative and communication. Technical
        # depth is close to irrelevant here, and there is no practical signal.
        "eval_weights": {
            "communication_score": 0.45,
            "presence_score": 0.25,
            "problem_solving_score": 0.20,
            "technical_score": 0.10,
        },
        "hooks": ["evaluate_star_response"],
    },

    "deep_dive": {
        # Deep dive drills one area to the bottom — depth and resume claims
        # holding up under questioning are the whole point.
        "eval_weights": {
            "technical_score": 0.45,
            "problem_solving_score": 0.25,
            "resume_alignment_score": 0.15,
            "communication_score": 0.15,
        },
        "hooks": [],
    },

    "leadership": {
        "eval_weights": {
            "communication_score": 0.35,
            "problem_solving_score": 0.30,
            "presence_score": 0.25,
            "technical_score": 0.10,
        },
        "hooks": ["evaluate_star_response"],
    },
}


def get_type_config(round_type: str) -> dict:
    """Return config for a round type, with fallback to technical defaults."""
    return INTERVIEW_TYPE_CONFIGS.get(round_type, {})


def get_persona_addendum(round_type: str) -> str:
    return get_type_config(round_type).get("persona_addendum", "")


def get_eval_weights(round_type: str) -> dict:
    defaults = {
        "technical_score": 0.35,
        "communication_score": 0.20,
        "problem_solving_score": 0.25,
        "practical_score": 0.20,
    }
    return get_type_config(round_type).get("eval_weights", defaults)
