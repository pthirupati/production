"""Technology-specific tutorial enrichment blocks (diagrams, shell, tables).

Replaces the old generic "Core concept → Run command → Expected output → Check
solution" boilerplate with practical, topic-aware content.
"""
from __future__ import annotations

import re

ENRICHMENT_HEADER = "## Architecture, commands & reference"
LEGACY_ENRICHMENT_HEADERS = (
    "## Cheat-sheet, diagram, and practice",
    ENRICHMENT_HEADER,
)

# Old auto-appended mermaid that showed up on every lesson.
_LEGACY_GENERIC_MERMAID = re.compile(
    r"\n+```mermaid\nflowchart LR\n\s+concept\[Core concept\].*?```\s*",
    re.DOTALL | re.I,
)


def strip_auto_enrichment(body: str) -> str:
    """Remove prior enrich_body appendices so content can be refreshed."""
    text = body or ""
    for header in LEGACY_ENRICHMENT_HEADERS:
        idx = text.find(header)
        if idx >= 0:
            text = text[:idx].rstrip()
    text = _LEGACY_GENERIC_MERMAID.sub("\n", text).rstrip()
    return text


def _topic_key(topic: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", (topic or "").lower()).strip("-")
    aliases = {
        "rhel-linux": "linux",
        "rhel": "linux",
        "shell-script": "shell",
        "bash": "shell",
        "k8s": "kubernetes",
        "amazon-web-services": "aws",
        "amazon-aws": "aws",
        "github-actions": "devops",
        "gitlab-ci": "devops",
        "jenkins": "devops",
        "argocd": "devops",
        "flux": "devops",
        "prometheus": "monitoring",
        "grafana": "monitoring",
        "mysql": "database",
        "postgresql": "database",
        "postgres": "database",
    }
    return aliases.get(key, key.split("-")[0] if key else "general")


def _profile_for(topic: str) -> dict:
    """Best-effort topic profile lookup (safe if curriculum import fails)."""
    try:
        from apps.tutorials.management.commands.curriculum.topic_profiles import get_profile
        return get_profile(topic) or {}
    except Exception:
        return {}


def architecture_diagram(
    topic: str,
    title: str = "",
    module: str = "",
    course_slug: str = "",
    profile: dict | None = None,
) -> str:
    """Return a Mermaid architecture/flow diagram for the technology track.

    Now per-course: build the diagram from the course's real components (curated
    registry or the topic profile). Fall back to the legacy per-key diagram only
    when no components are available.
    """
    if profile is None:
        profile = _profile_for(topic)
    from apps.tutorials.course_diagrams import course_architecture_diagram

    per_course = course_architecture_diagram(
        topic, profile=profile, course_slug=course_slug, module=module, title=title
    )
    if per_course:
        return per_course

    key = _topic_key(topic)
    label = re.sub(r"[^A-Za-z0-9 _-]", "", (module or title or topic))[:48] or "Lesson"
    charts: dict[str, str] = {
        "linux": (
            "flowchart TB\n"
            "  subgraph host [Linux host]\n"
            "    SHELL[Shell / systemd] --> FS[Filesystem & permissions]\n"
            "    FS --> NET[Network stack]\n"
            "    NET --> LOGS[journald / audit]\n"
            "  end\n"
            "  OPS[Operator] --> SHELL"
        ),
        "kubernetes": (
            "flowchart LR\n"
            "  subgraph cluster [Kubernetes cluster]\n"
            "    API[API server] --> ETCD[(etcd)]\n"
            "    API --> SCH[Scheduler]\n"
            "    SCH --> KUBELET[kubelet]\n"
            "    KUBELET --> POD[Pods & Services]\n"
            "  end\n"
            "  DEV[kubectl / helm] --> API"
        ),
        "docker": (
            "flowchart LR\n"
            "  IMG[Image layers] --> RT[containerd / runtime]\n"
            "  RT --> CTR[Containers]\n"
            "  CTR --> NET[Bridge / overlay network]\n"
            "  CTR --> VOL[Named volumes]"
        ),
        "aws": (
            "flowchart TB\n"
            "  subgraph account [AWS account]\n"
            "    IAM[IAM roles & policies] --> VPC[VPC / subnets]\n"
            "    VPC --> EC2[EC2 / ASG]\n"
            "    VPC --> RDS[(RDS)]\n"
            "    S3[(S3)] --- EC2\n"
            "  end\n"
            "  CLI[AWS CLI / Console] --> IAM"
        ),
        "terraform": (
            "flowchart LR\n"
            "  HCL[.tf configuration] --> PLAN[terraform plan]\n"
            "  PLAN --> STATE[(remote state)]\n"
            "  PLAN --> APPLY[terraform apply]\n"
            "  APPLY --> RES[Cloud resources]"
        ),
        "ansible": (
            "flowchart LR\n"
            "  INV[inventory] --> PLAY[playbook]\n"
            "  PLAY --> TASKS[tasks / handlers]\n"
            "  TASKS --> HOSTS[managed hosts]\n"
            "  HOSTS --> FACTS[facts & idempotency]"
        ),
        "devops": (
            "flowchart LR\n"
            "  GIT[Git commit] --> CI[CI pipeline]\n"
            "  CI --> TEST[build & test]\n"
            "  TEST --> SCAN[security scan]\n"
            "  SCAN --> CD[deploy / GitOps]\n"
            "  CD --> PROD[production]"
        ),
        "python": (
            "flowchart LR\n"
            "  SRC[.py modules] --> VENV[virtualenv]\n"
            "  VENV --> TEST[pytest]\n"
            "  TEST --> PKG[package / API]\n"
            "  PKG --> RUN[runtime / container]"
        ),
        "database": (
            "flowchart TB\n"
            "  APP[Application] --> POOL[connection pool]\n"
            "  POOL --> PRIMARY[(primary DB)]\n"
            "  PRIMARY --> REPLICA[(read replica)]\n"
            "  PRIMARY --> BACKUP[backup / PITR]"
        ),
        "networking": (
            "flowchart LR\n"
            "  CLIENT[Client] --> FW[firewall / ACL]\n"
            "  FW --> ROUTE[routing table]\n"
            "  ROUTE --> SRV[service host]\n"
            "  SRV --> DNS[DNS resolution]"
        ),
        "security": (
            "flowchart TB\n"
            "  IDP[Identity provider] --> IAM[IAM / RBAC]\n"
            "  IAM --> APP[Application]\n"
            "  APP --> DATA[(sensitive data)]\n"
            "  LOGS[audit logs] --- IAM"
        ),
        "monitoring": (
            "flowchart LR\n"
            "  TARGETS[exporters / apps] --> PROM[Prometheus scrape]\n"
            "  PROM --> RULES[alert rules]\n"
            "  PROM --> GRAF[Grafana dashboards]\n"
            "  RULES --> ONCALL[on-call]"
        ),
        "vmware": (
            "flowchart TB\n"
            "  subgraph vsphere [vSphere]\n"
            "    VC[vCenter] --> HOST[ESXi hosts]\n"
            "    HOST --> VM[Virtual machines]\n"
            "    VM --> DATASTORE[(datastore)]\n"
            "  end"
        ),
        "windows": (
            "flowchart LR\n"
            "  AD[Active Directory] --> SRV[Windows Server]\n"
            "  SRV --> SVC[Windows services]\n"
            "  SVC --> EVT[Event logs]"
        ),
        "shell": (
            "flowchart LR\n"
            "  SCRIPT[.sh script] --> ENV[environment / PATH]\n"
            "  ENV --> EXEC[bash execution]\n"
            "  EXEC --> PIPE[pipes & redirects]\n"
            "  PIPE --> EXIT[exit codes]"
        ),
    }
    chart = charts.get(key, (
        f"flowchart LR\n"
        f"  subgraph lesson [{label}]\n"
        f"    READ[Study] --> PRACTICE[Hands-on]\n"
        f"    PRACTICE --> DEBUG[Troubleshoot]\n"
        f"    DEBUG --> VALIDATE[Validate in lab]\n"
        f"  end"
    ))
    return f"```mermaid\n{chart}\n```"


def shell_practice_block(topic: str, title: str = "") -> str:
    """Practical shell/code example with realistic commands for the topic."""
    key = _topic_key(topic)
    examples: dict[str, str] = {
        "linux": (
            "```bash\n"
            "# Inspect identity and permissions\n"
            "getent passwd appuser\n"
            "id appuser\n"
            "ls -la /home/appuser\n"
            "systemctl status sshd --no-pager\n"
            "\n"
            "# Expected: user record, uid/gid, home listing, active sshd\n"
            "```"
        ),
        "kubernetes": (
            "```bash\n"
            "kubectl get pods -A -o wide\n"
            "kubectl describe pod <name> -n <namespace>\n"
            "kubectl logs <name> -n <namespace> --tail=80\n"
            "kubectl get events -n <namespace> --sort-by=.lastTimestamp\n"
            "```"
        ),
        "docker": (
            "```bash\n"
            "docker ps -a\n"
            "docker logs <container> --tail 50\n"
            "docker inspect <container> --format '{{.State.Status}}'\n"
            "```"
        ),
        "aws": (
            "```bash\n"
            "aws sts get-caller-identity\n"
            "aws ec2 describe-instances --query 'Reservations[].Instances[].State.Name'\n"
            "aws s3 ls\n"
            "```"
        ),
        "terraform": (
            "```bash\n"
            "terraform init\n"
            "terraform validate\n"
            "terraform plan -out=tfplan\n"
            "terraform apply tfplan\n"
            "```"
        ),
        "ansible": (
            "```bash\n"
            "ansible-inventory --list\n"
            "ansible all -m ping\n"
            "ansible-playbook site.yml --check\n"
            "ansible-playbook site.yml\n"
            "```"
        ),
        "devops": (
            "```bash\n"
            "# Typical CI troubleshooting\n"
            "git log -1 --oneline\n"
            "gh run list --limit 3\n"
            "gh run view <id> --log-failed\n"
            "```"
        ),
        "python": (
            "```python\n"
            "import sys\n"
            "print(sys.version)\n"
            "# Run tests for the module under study\n"
            "# pytest -q tests/\n"
            "```"
        ),
        "database": (
            "```bash\n"
            "# PostgreSQL example\n"
            "psql -c \"\\l\"\n"
            "psql -c \"SELECT pid, state, query FROM pg_stat_activity;\"\n"
            "```"
        ),
        "monitoring": (
            "```promql\n"
            "up\n"
            "up == 0\n"
            "sum by (job) (up)\n"
            "```"
        ),
        "networking": (
            "```bash\n"
            "ip addr show\n"
            "ip route\n"
            "ping -c 3 <host>\n"
            "dig +short <name>\n"
            "```"
        ),
        "security": (
            "```bash\n"
            "sudo ss -tlnp\n"
            "sudo grep -i failed /var/log/auth.log | tail -5\n"
            "sudo ufw status verbose\n"
            "```"
        ),
        "windows": (
            "```powershell\n"
            "Get-Service | Where-Object Status -eq 'Stopped'\n"
            "Get-EventLog -LogName System -Newest 15\n"
            "Test-NetConnection <host> -Port 443\n"
            "```"
        ),
        "vmware": (
            "```bash\n"
            "# vSphere CLI (govc) style inspection\n"
            "govc vm.info <vm>\n"
            "govc device.ls -vm <vm>\n"
            "```"
        ),
        "shell": (
            "```bash\n"
            "set -euo pipefail\n"
            "bash -n script.sh    # syntax check\n"
            "shellcheck script.sh\n"
            "bash -x script.sh    # trace execution\n"
            "```"
        ),
    }
    example = examples.get(key)
    if example is not None:
        # Pair the example commands with realistic sample output so the
        # ShellBlock output pane / "compare to baseline" has content.
        from apps.tutorials.course_diagrams import shell_block_with_output

        # promql/powershell examples keep their own fenced block; only rebuild
        # bash-style examples where sample output is meaningful.
        if example.startswith("```bash"):
            inner = example.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
            with_output = shell_block_with_output(inner, topic, title)
            if with_output:
                return with_output
        return example
    return (
        "```bash\n"
        f"# Hands-on inspection for: {title or topic}\n"
        "echo \"inspect → change one thing → verify with the same command\"\n"
        "```"
    )


def reference_table(topic: str, title: str = "") -> str:
    """Topic-specific cheat-sheet table."""
    key = _topic_key(topic)
    rows: dict[str, list[tuple[str, str, str]]] = {
        "linux": [
            ("User / group", "`id user` · `getent passwd user`", "Confirm identity before permission changes"),
            ("Service", "`systemctl status svc`", "See active/failed state and recent lines"),
            ("Logs", "`journalctl -u svc -e`", "Correlate errors with service restarts"),
        ],
        "kubernetes": [
            ("Workload", "`kubectl get pods -A`", "Find crashing or pending pods"),
            ("Events", "`kubectl describe pod`", "See scheduling / image pull failures"),
            ("Logs", "`kubectl logs pod`", "Read application error output"),
        ],
        "aws": [
            ("Identity", "`aws sts get-caller-identity`", "Confirm account and role"),
            ("Compute", "`aws ec2 describe-instances`", "Instance state and networking"),
            ("Storage", "`aws s3 ls`", "Bucket visibility and permissions"),
        ],
        "terraform": [
            ("Syntax", "`terraform validate`", "Catch HCL errors before plan"),
            ("Plan", "`terraform plan`", "Preview infrastructure diff"),
            ("State", "`terraform state list`", "See managed resource addresses"),
        ],
        "devops": [
            ("Pipeline", "`gh run view --log-failed`", "Find failing CI step quickly"),
            ("Git", "`git log -p -1`", "See last change that may have broken build"),
            ("Deploy", "GitOps sync / rollout status", "Confirm new revision is live"),
        ],
    }
    default = [
        (f"{topic} inspect", "Run the lesson's primary command", "Establish baseline before changes"),
        ("Safety", "Snapshot / backup / dry-run", "Keep changes reversible"),
        ("Validation", "Re-run inspection + lab check", "Prove the fix stuck"),
    ]
    lines = [
        "| What to check | Command / signal | Why it matters |",
        "|---|---|---|",
    ]
    for what, cmd, why in rows.get(key, default):
        lines.append(f"| {what} | {cmd} | {why} |")
    return "\n".join(lines)


def practical_summary(topic: str, title: str = "") -> str:
    """Short practical playbook instead of a generic lesson checklist."""
    lesson = title or topic
    return (
        f"### Hands-on playbook — {lesson}\n\n"
        "1. **Read the architecture diagram** above and note which component you will touch.\n"
        "2. **Run the inspection commands** in the shell block and save the output as your baseline.\n"
        "3. **Make one reversible change** (config, flag, or resource) that targets the symptom.\n"
        "4. **Re-run the same commands** and compare output to the baseline.\n"
        "5. **Open the linked lab** and validate your fix under realistic incident pressure."
    )


# Illustration assets live in frontend/public/tutorials/illustrations/{key}.svg
_ILLUSTRATION_KEYS = frozenset({
    "linux", "kubernetes", "docker", "aws", "terraform", "ansible", "devops",
    "python", "database", "monitoring", "networking", "security", "windows",
    "vmware", "shell", "javascript", "react", "java", "html", "nodejs", "gpu", "ai",
})

_ILLUSTRATIONS_DIR = None
_TOPIC_TO_COURSE = None


def _illustrations_dir():
    global _ILLUSTRATIONS_DIR
    if _ILLUSTRATIONS_DIR is None:
        from pathlib import Path
        # backend/apps/tutorials/tutorial_enrichment.py -> parents[3] == repo root
        _ILLUSTRATIONS_DIR = (
            Path(__file__).resolve().parents[3]
            / "frontend" / "public" / "tutorials" / "illustrations"
        )
    return _ILLUSTRATIONS_DIR


def _topic_to_course_map() -> dict[str, str]:
    """Map a slugified topic to its primary course_slug (for per-course SVGs).

    Built once from the course catalog; falls back to empty on any import
    failure so illustration selection degrades to the per-key SVG.
    """
    global _TOPIC_TO_COURSE
    if _TOPIC_TO_COURSE is None:
        mapping: dict[str, str] = {}
        try:
            from apps.tutorials.management.commands.course_catalog import (
                all_course_definitions,
            )
            for course in all_course_definitions():
                cs = course.get("course_slug", "")
                ts = re.sub(r"[^a-z0-9]+", "-", (course.get("topic") or "").lower()).strip("-")
                if ts and cs and ts not in mapping:
                    mapping[ts] = cs
        except Exception:
            mapping = {}
        _TOPIC_TO_COURSE = mapping
    return _TOPIC_TO_COURSE


def _illustration_key(topic: str, course_slug: str = "") -> str:
    """Pick the best available SVG: per-course → per-key → general."""
    dir_ = _illustrations_dir()

    def _exists(name: str) -> bool:
        try:
            return (dir_ / f"{name}.svg").is_file()
        except Exception:
            return False

    cs = re.sub(r"[^a-z0-9]+", "-", (course_slug or "").lower()).strip("-")
    if cs and _exists(cs):
        return cs
    ts = re.sub(r"[^a-z0-9]+", "-", (topic or "").lower()).strip("-")
    mapped = _topic_to_course_map().get(ts)
    if mapped and _exists(mapped):
        return mapped
    key = _topic_key(topic)
    if key in _ILLUSTRATION_KEYS and _exists(key):
        return key
    if _exists(key):
        return key
    return "general"


def topic_illustration(topic: str, title: str = "", course_slug: str = "") -> str:
    """Markdown hero image for a lesson — maps each course to its own SVG.

    Prefers the per-course illustration (distinct per course_slug), then the
    per-technology SVG, and finally general.svg only when nothing matches.
    """
    key = _illustration_key(topic, course_slug)
    label = re.sub(r"[^A-Za-z0-9 _-]", "", (title or topic))[:64] or key.title()
    return f"![{label} — architecture overview](/tutorials/illustrations/{key}.svg)"


def fix_broken_prose(text: str) -> str:
    """Repair line-wrap hyphenation and glued words from bulk seeding."""
    if not text:
        return text
    # configura- tion → configuration (soft hyphen across lines)
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Common seed typos / missing spaces
    fixes = (
        (r"\btutorela\b", "tutorial"),
        (r"\btutorelas\b", "tutorials"),
        (r"\bmnay\b", "many"),
        (r"\beperince\b", "experience"),
        (r"\btechnolpogy\b", "technology"),
        (r"\bscinario\b", "scenario"),
        (r"\bscinarios\b", "scenarios"),
        (r"\bscinarp\b", "script"),
        (r"\bceritifate\b", "certificate"),
        (r"\bconfiguraton\b", "configuration"),
        (r"\bconfigura\s*tion\b", "configuration"),
        (r"\barchitecure\b", "architecture"),
        (r"\bfrom ero\b", "from zero"),
        (r"\bsratch\b", "scratch"),
        (r"\bteh\b", "the"),
        (r"\bwiht\b", "with"),
        (r"\btaht\b", "that"),
        (r"\bhte\b", "the"),
        (r"\brecieve\b", "receive"),
        (r"\boccured\b", "occurred"),
        (r"\bseperate\b", "separate"),
        (r"\bdefinately\b", "definitely"),
        (r"\benviroment\b", "environment"),
        (r"\bparamaters\b", "parameters"),
        (r"\bpriviledge\b", "privilege"),
        (r"\bauthentica\s*tion\b", "authentication"),
        (r"\bauthoriza\s*tion\b", "authorization"),
    )
    for pat, repl in fixes:
        text = re.sub(pat, repl, text, flags=re.I)
    return text
