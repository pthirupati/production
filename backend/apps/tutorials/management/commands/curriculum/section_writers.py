"""
Lean, high-signal tutorial section writers — six sections per module.

Redesigned (2026-07) from the old 20-section structure to a concise, non-repetitive
lesson that reads in a few minutes:

    1. Overview                 — what/why + ONE architecture diagram        (Learn)
    2. Key concepts             — 3-5 module-specific concepts + one table    (Learn)
    3. Hands-on walkthrough     — real commands + ONE sequenceDiagram         (Practice)
    4. Common pitfalls & fixes  — 3-5 real failure modes + the fix            (Operate)
    5. Practice & assess        — linked-lab CTA + 5-question quiz            (Assess)
    6. Key takeaways            — 4-6 bullets + further reading               (Assess)

De-duplication guarantee: exactly ONE architecture (flowchart) diagram in Overview
and exactly ONE sequenceDiagram in the walkthrough — no diagram is repeated in any
other section, and enrichment no longer injects a diagram/image/table per section.

Everything is deterministic and offline — no clock, no RNG. Any variation is seeded
from a stable hash of topic+module (see course_diagrams.stable_hash).
"""

from __future__ import annotations

import re

from .book_chapter import get_book_body
from .topic_profiles import get_profile

LEVEL_LABELS = {
    "beginner": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
    "expert": "Expert",
    "enterprise": "Real Enterprise",
}

# (heading, section_key). Order == render order. The heading text is chosen so the
# frontend's phaseFor() (TutorialDetail.jsx) maps each into the right phase:
#   Overview / Key concepts -> Learn ; Hands-on walkthrough -> Practice ;
#   Common pitfalls -> Operate ; Practice & assess / Key takeaways -> Assess.
SECTION_HEADINGS: list[tuple[str, str]] = [
    ("Overview", "overview"),
    ("Key concepts", "concepts"),
    ("Hands-on walkthrough", "walkthrough"),
    ("Common pitfalls & fixes", "pitfalls"),
    ("Practice & assess", "assess"),
    ("Key takeaways", "takeaways"),
]


def _kw(module: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[a-zA-Z0-9]+", module) if len(w) > 2}


def _match_concepts(profile: dict, module: str) -> list[tuple[str, str]]:
    """Return (name, description) concept pairs most relevant to THIS module.

    Prefers concepts whose key overlaps the module title; falls back to the
    first few profile concepts so a lesson is never empty.
    """
    concepts = profile.get("concepts") or {}
    if not concepts:
        return []
    keys = _kw(module)
    matched: list[tuple[str, str]] = []
    for key, text in concepts.items():
        parts = set(key.lower().replace("_", " ").split())
        if keys & parts or any(p in module.lower() for p in parts):
            matched.append((key.replace("_", " ").title(), text))
    if not matched:
        matched = [
            (k.replace("_", " ").title(), v) for k, v in list(concepts.items())[:4]
        ]
    return matched[:5]


def _components(profile: dict) -> list[str]:
    comps = profile.get("engines") or profile.get("components") or []
    if isinstance(comps, str):
        comps = [c.strip() for c in comps.split(",") if c.strip()]
    return [c for c in comps if c][:4]


def _arch_diagram(module: str, profile: dict, topic: str = "", course_slug: str = "") -> str:
    """The single per-course architecture flowchart (Overview only)."""
    from apps.tutorials.course_diagrams import course_architecture_diagram

    per_course = course_architecture_diagram(
        topic, profile=profile, course_slug=course_slug, module=module
    )
    if per_course:
        return per_course

    # Fall back to the per-technology diagram library (also a single flowchart).
    from apps.tutorials.tutorial_enrichment import architecture_diagram

    return architecture_diagram(topic, module=module, course_slug=course_slug, profile=profile)


# ── Topic-specific pitfalls ────────────────────────────────────────────────
# Real failure modes + the fix, keyed by a slugified topic (matched by substring
# so "PostgreSQL"/"MySQL" hit the database entry, etc.). Each pitfall is
# (symptom, fix). Concrete and topic-specific — this is the highest-value section.

_PITFALLS: dict[str, list[tuple[str, str]]] = {
    "linux": [
        ("A service won't start and `systemctl status` only says `failed`.",
         "Read the real error with `journalctl -u <svc> -b --no-pager`; a bad config path or missing user is almost always in the last 10 lines."),
        ("`Permission denied` even though the file mode looks right.",
         "Check the *directory* execute bit and SELinux context (`ls -Z`, `getenforce`). A denied AVC won't show in `ls -l` — use `ausearch -m avc -ts recent`."),
        ("Disk shows free space but writes fail with `No space left on device`.",
         "You've run out of inodes, not blocks. Confirm with `df -i` and clean up the directory with millions of tiny files."),
        ("Editing `/etc/fstab` wrong makes the box unbootable.",
         "Always add `nofail` to non-critical mounts and validate with `mount -a` before rebooting."),
    ],
    "kubernetes": [
        ("Pod stuck in `Pending` forever.",
         "`kubectl describe pod` — it's almost always unschedulable due to resource requests, a missing node label/taint toleration, or an unbound PVC."),
        ("Pod in `CrashLoopBackOff`.",
         "`kubectl logs <pod> --previous` shows the crash from the *last* attempt; the current container may be too young to have logged yet."),
        ("`ImagePullBackOff` on a private image.",
         "The node can't authenticate — attach an `imagePullSecret` to the ServiceAccount, and verify the registry path/tag actually exists."),
        ("Service has endpoints but traffic 503s.",
         "The Service `selector` doesn't match the Pod labels, or the readiness probe is failing so Pods never join `Endpoints`. Check `kubectl get endpoints <svc>`."),
        ("`kubectl apply` succeeds but nothing changes.",
         "You applied to the wrong context/namespace. Confirm with `kubectl config current-context` and `-n`."),
    ],
    "docker": [
        ("Container exits immediately with code 0 or 1.",
         "The main process finished — a container lives only as long as PID 1. Run `docker logs <ctr>` and make sure `CMD` starts a foreground, long-running process."),
        ("Image is huge and slow to build.",
         "Order `COPY`/`RUN` so dependency installs are cached; copy `requirements`/`package.json` before source. Use a slim base and a `.dockerignore`."),
        ("`port already allocated` on `docker run -p`.",
         "Another container/host process owns the host port. Find it with `docker ps` / `ss -tlnp` and pick a different left-hand `-p HOST:CONTAINER` value."),
        ("Data disappears when the container is removed.",
         "The writable layer is ephemeral. Persist state in a named volume (`-v data:/var/lib/...`), not the container filesystem."),
    ],
    "terraform": [
        ("`terraform apply` wants to destroy/recreate a resource you only renamed.",
         "Terraform keys on the resource address, not the cloud name. Use `terraform state mv` (or `moved` blocks) to rename without recreating."),
        ("Two people run apply and corrupt state.",
         "Enable a remote backend with state locking (S3 + DynamoDB, or TFC). Never share a local `terraform.tfstate`."),
        ("Plan shows changes every run even though nothing changed.",
         "Perpetual drift from a provider default or an attribute the API normalizes. Pin it explicitly or add a `lifecycle { ignore_changes = [...] }`."),
        ("A secret ends up in state in plaintext.",
         "State is sensitive by design — encrypt the backend and restrict access; mark outputs `sensitive = true`. Never commit state to Git."),
    ],
    "ansible": [
        ("Playbook reports `changed` every run for a task that should be idempotent.",
         "You used `command`/`shell` where a real module exists. Switch to the module (e.g. `package`, `copy`, `lineinfile`) so state is compared, not blindly re-run."),
        ("`UNREACHABLE` on hosts that you can SSH to by hand.",
         "Ansible uses its own SSH config/user. Set `ansible_user`/`ansible_ssh_private_key_file` and test with `ansible <host> -m ping`."),
        ("A privileged task fails with permission errors.",
         "You forgot `become: true` (or `-b`). Privilege escalation is off by default per play/task."),
        ("Variables resolve to the wrong value.",
         "Ansible variable precedence bit you — `-e` extra-vars beat everything, role defaults lose to almost everything. Print with `debug: var=...` to confirm."),
    ],
    "aws": [
        ("`AccessDenied` even though the IAM policy looks correct.",
         "An SCP, permissions boundary, or resource policy is denying — an explicit `Deny` always wins. Use the IAM Policy Simulator to see which statement blocks you."),
        ("EC2 instance is `running` but you can't SSH in.",
         "Security group, NACL, route table, or a missing public IP. Work outward: SG inbound 22 from your IP, then subnet route to an IGW."),
        ("S3 objects return 403 despite a public bucket policy.",
         "Block Public Access is on at the account/bucket level and overrides the policy, or object ownership/ACLs disagree. Prefer bucket policies + BPA off only where truly needed."),
        ("Surprise NAT Gateway / data-transfer bill.",
         "Cross-AZ and NAT egress cost real money. Use VPC endpoints for S3/DynamoDB and keep chatty traffic in one AZ."),
    ],
    "database": [
        ("A query that was fast is suddenly slow.",
         "Stale statistics or a plan flip. Run `EXPLAIN (ANALYZE, BUFFERS)`, then `ANALYZE` the table; check the index is actually used, not a seq scan."),
        ("Connections pile up and the app times out.",
         "You've exhausted `max_connections`. Put a pooler (PgBouncer/ProxySQL) in front and cap per-app pool size — apps rarely need hundreds of direct connections."),
        ("Table keeps growing on disk after you delete rows.",
         "MVCC/dead-tuple bloat. `DELETE` doesn't reclaim space — tune autovacuum, or `VACUUM (FULL)` in a window; monitor dead tuples in `pg_stat_user_tables`."),
        ("Replica lag spikes under load.",
         "A long-running query or a write burst on the primary. Watch `pg_stat_replication`; offload heavy reads and avoid huge single transactions."),
        ("A restore fails during a real incident.",
         "The backup was never tested. Practice restores on a schedule — an untested backup is a hope, not a recovery plan."),
    ],
    "python": [
        ("`ModuleNotFoundError` even though you `pip install`ed the package.",
         "Wrong interpreter/venv. Confirm with `which python` and `python -m pip list`; activate the venv or use `python -m pip install`."),
        ("Mutable default argument keeps state between calls.",
         "`def f(x=[])` shares one list across calls. Use `def f(x=None): x = x or []`."),
        ("A script works locally but breaks in CI/prod.",
         "Unpinned dependencies or relying on the system Python. Pin versions in `requirements.txt`/lockfile and run tests in the same container image."),
        ("Long-running async tool stalls.",
         "A blocking call (sync I/O, `time.sleep`) inside the event loop. Move it to `asyncio.to_thread`/an executor, or use an async client."),
    ],
    "git": [
        ("You committed to the wrong branch.",
         "`git switch -c right-branch` then `git reset --hard origin/main` on the original — or `git cherry-pick`/`git reset --soft HEAD~1` to move the change."),
        ("A merge conflict looks unresolvable.",
         "Conflicts are only overlapping edits. Open the file, keep the correct hunk between the markers, `git add`, then continue — or `git merge --abort` to retreat."),
        ("A secret got committed.",
         "Rotate it immediately — history is public once pushed. Rewriting history (`git filter-repo`) helps, but the secret is already compromised."),
        ("`detached HEAD` and you're worried you lost work.",
         "You didn't. `git reflog` shows every commit you were on; create a branch from the hash you want."),
    ],
    "networking": [
        ("`ping` works but the app can't connect.",
         "ICMP is L3; the app is L4/L7. Test the actual port with `nc -vz host port` or `ss -tlnp`, and check firewall/security-group rules for that port."),
        ("DNS resolves to the wrong/old IP.",
         "Caching. Check the record's TTL and query the authoritative server directly with `dig @ns example.com`; flush local caches."),
        ("Intermittent packet loss or slow transfers.",
         "MTU/fragmentation or a duplex mismatch. Test path MTU (`ping -M do -s ...`) and check interface error counters."),
        ("Traffic takes an unexpected path.",
         "A more-specific or wrong static route wins. Inspect with `ip route get <dst>` — longest-prefix match decides, not order."),
    ],
    "security": [
        ("Over-broad IAM/RBAC grants that nobody remembers approving.",
         "Start from deny, grant least privilege, and review access regularly. Wildcards (`*`) in policies are how one leaked key becomes a full breach."),
        ("Secrets in environment files or Git history.",
         "Move them to a vault with rotation and audit; scan the repo history and rotate anything found. Env files leak via logs and images."),
        ("TLS 'works' but trusts anything.",
         "Certificate validation was disabled to 'make it work'. Fix the trust chain instead — a disabled check means no encryption guarantee."),
        ("Alerts fire constantly so real ones get ignored.",
         "Tune detections to be actionable and map them to a runbook. Alert fatigue is itself a vulnerability."),
    ],
    "monitoring": [
        ("Dashboards are green but users report an outage.",
         "You're measuring the wrong SLI (host up, not request success). Alert on user-facing symptoms (error rate/latency), not just resource metrics."),
        ("Alerts are noisy and page at 3am for nothing.",
         "Threshold alerting on a spiky metric. Use multi-window burn-rate alerts on an SLO so you page on sustained budget burn, not transient blips."),
        ("A dashboard query is slow or times out.",
         "Unbounded high-cardinality labels. Aggregate with `sum by (...)`, add recording rules, and drop labels you never query."),
        ("You can't tell *why* something is slow.",
         "Metrics show 'what', not 'why'. Add traces/exemplars so a latency spike links to the exact slow span."),
    ],
    "vmware": [
        ("A VM is slow but guest CPU looks fine.",
         "Check %CPU Ready in esxtop/vCenter — the VM is waiting for physical cores. Reduce oversized vCPUs and host contention."),
        ("Snapshots quietly fill the datastore.",
         "Snapshots are deltas that grow forever. Consolidate/delete them promptly; never treat a snapshot as a backup."),
        ("vMotion fails or a VM won't power on after a host issue.",
         "EVC/CPU compatibility or an orphaned lock. Check host CPU baseline and clear stale `.lck` files; verify shared datastore access."),
        ("Storage latency spikes under load.",
         "Datastore contention or a failing path. Watch DAVG/KAVG in esxtop and check multipathing before blaming the app."),
    ],
    "windows": [
        ("Group Policy change doesn't apply.",
         "Replication/precedence. Run `gpupdate /force`, check `gpresult /r` for the winning GPO, and confirm the OU link and security filtering."),
        ("A service fails to start after a reboot.",
         "A dependency or logon-account issue. Read the specific error in Event Viewer (System log) and check the service's recovery/dependency settings."),
        ("AD authentication intermittently fails.",
         "Time skew or DNS. Kerberos breaks past a 5-minute clock difference — verify `w32tm` sync and that clients point at the DC for DNS."),
    ],
    "shell": [
        ("Script breaks on filenames with spaces.",
         "Unquoted expansion. Always quote: `\"$var\"`, `\"$@\"`; run `shellcheck` to catch it automatically."),
        ("A failing command in the middle doesn't stop the script.",
         "Bash keeps going by default. Start scripts with `set -euo pipefail` so errors, unset vars, and pipe failures abort."),
        ("`command not found` in cron but works in your shell.",
         "Cron has a minimal `PATH` and no profile. Use absolute paths or set `PATH` at the top of the script."),
    ],
}

# Generic (but still useful) fallback pitfalls for topics without a curated entry.
_GENERIC_PITFALLS: list[tuple[str, str]] = [
    ("A change 'works on my machine' but fails in production.",
     "The environments differ — pin versions and mirror production topology in staging before you ship."),
    ("A restart 'fixes' the problem, so nobody finds root cause.",
     "Capture logs/metrics BEFORE restarting; a restart clears the very evidence you need and the issue returns."),
    ("A change to production has no rollback plan.",
     "Change incrementally behind a flag and know the exact revert command before you touch prod."),
    ("An alert fired but nobody knew what to do.",
     "Every alert must be actionable and linked to a runbook; delete or tune alerts that page without a next step."),
]


def _pitfalls_for(topic: str, course_slug: str = "") -> list[tuple[str, str]]:
    hay = f"{course_slug} {topic}".lower()
    for key, items in _PITFALLS.items():
        if key in hay:
            return items
    return _GENERIC_PITFALLS


def _level_note(level: str) -> str:
    return {
        "beginner": "At this level, focus on safe read-only exploration before making changes.",
        "intermediate": "Connect this to adjacent systems (network, identity, storage) and validate in staging.",
        "advanced": "Focus on failure modes, automation, and a measurable rollback plan.",
        "expert": "You should lead design reviews and defend trade-offs with latency/cost/risk data.",
        "enterprise": "Operate under change control, audited access, and contractual SLAs.",
    }.get(level, "")


# ── Section writers ─────────────────────────────────────────────────────────


def _write_overview(topic: str, module: str, level: str, profile: dict, course_slug: str = "") -> str:
    tagline = (profile.get("tagline") or topic).rstrip(".")
    arch = profile.get("architecture", "")
    diagram = _arch_diagram(module, profile, topic=topic, course_slug=course_slug)
    body = (
        f"## Overview\n\n"
        f"**{module}** teaches one focused part of {topic}: {tagline.lower()}. "
        f"You'll leave able to explain what it is, run the core commands, and recognise the failures it causes when it's wrong.\n\n"
    )
    if arch:
        body += f"**How it fits together:** {arch}\n\n"
    body += (
        "The diagram below is the mental model for this module — the single picture to keep in your head. "
        "Everything in the walkthrough moves through these components.\n\n"
        f"{diagram}"
    )
    return body


def _write_concepts(topic: str, module: str, level: str, profile: dict) -> str:
    items = _match_concepts(profile, module)
    body = (
        f"## Key concepts\n\n"
        f"The ideas that actually matter for **{module}** — you should be able to explain each in one sentence.\n\n"
    )
    if items:
        body += "\n".join(f"- **{name}** — {desc}" for name, desc in items)
    else:
        body += (
            f"- **Control plane** — where {topic} configuration and policy live.\n"
            f"- **Data plane** — where the real traffic/workload is served.\n"
            f"- **Idempotency** — repeating an operation converges to the same state.\n"
            f"- **Blast radius** — what breaks downstream when this fails."
        )
    # At most ONE comparison table, and only where a control/data split is genuinely useful.
    body += (
        "\n\n| Term | What it means | How to verify |\n"
        "|---|---|---|\n"
        f"| {module} | The subject of this module | Its status/health check returns healthy |\n"
        "| Control plane | Manages configuration & policy | API/UI responds; no config drift |\n"
        "| Data plane | Serves user/workload traffic | End-to-end synthetic check passes |\n"
    )
    return body


def _write_walkthrough(topic: str, module: str, level: str, profile: dict, playground: str) -> str:
    from apps.tutorials.course_diagrams import (
        command_sequence_diagram,
        shell_block_with_output,
    )

    cmds = profile.get("commands") or {}
    fb = _fallback_for(topic)
    if not cmds and fb:
        cmds = {"steps": fb[1].get("labs", "")}

    shell = shell_block_with_output(cmds, topic, module)
    if not shell:
        first = next(iter(cmds.values()), f"# Practice {module}\nhelp | head -5")
        shell = f"```bash\n{first}\n```"

    seq = command_sequence_diagram(cmds, topic, module)
    seq_block = (
        f"\n\nThe same steps as an interaction — who talks to what, in order:\n\n{seq}"
        if seq
        else ""
    )
    return (
        f"## Hands-on walkthrough\n\n"
        f"Run these in the **{topic}** playground (`{playground}`) or the linked lab. "
        f"Each line is prefixed with `$`; the lines below it are the output you should expect, so you can compare "
        f"your terminal to the baseline after every command.\n\n"
        f"{shell}\n\n"
        f"> [!TIP] Change one thing, then re-run the same command and diff the output against the baseline above. "
        f"That diff is your evidence the change did what you intended.{seq_block}"
    )


def _write_pitfalls(topic: str, module: str, level: str, profile: dict, course_slug: str = "") -> str:
    pitfalls = _pitfalls_for(topic, course_slug)
    body = (
        f"## Common pitfalls & fixes\n\n"
        f"The failures that actually bite people with {topic}. For each, the symptom you'll see and the fix.\n\n"
    )
    for i, (symptom, fix) in enumerate(pitfalls, start=1):
        body += f"**{i}. {symptom}**\n\n{fix}\n\n"
    body += (
        "> [!GOTCHA] Before any invasive action, capture logs and current state first — "
        "a blind restart often clears the very evidence you need for root cause."
    )
    return body


def _write_assess(topic: str, module: str, level: str, profile: dict, playground: str, scenario: str) -> str:
    lab_line = (
        f"[Run in lab →](/scenarios/{scenario})"
        if scenario
        else f"Open the **{topic}** playground (`{playground}`) and reproduce a failure, then fix it."
    )
    return (
        f"## Practice & assess\n\n"
        f"**Do the lab.** {lab_line}\n\n"
        f"Reproduce the failure, apply one fix at a time, and verify with the same commands from the walkthrough. "
        f"Use **Check Solution** — the lab grades real system state, not marker files.\n\n"
        f"**Then take the quiz.** Answer the five-question module quiz below. "
        f"You pass this lesson when your quiz score is **80% or higher** and the linked hands-on lab is complete. "
        f"{_level_note(level)}"
    )


def _write_takeaways(topic: str, module: str, level: str, profile: dict) -> str:
    concepts = _match_concepts(profile, module)
    slo = profile.get("slo", "availability, latency p99, error rate, saturation")
    bullets = [
        f"**{module}** exists to {profile.get('tagline', topic).rstrip('.').lower()} — keep the Overview diagram as your mental model.",
        "Automate it (IaC/GitOps) and keep changes small; make the secure path the easy path.",
        f"Watch the signals that matter here: {slo}.",
        "Least privilege + secrets in a vault (never Git) + encryption in transit and at rest.",
        "A fix is only done when a measurable signal (SLO/health check/test) confirms recovery — then write the runbook line.",
    ]
    if concepts:
        bullets.insert(1, f"The concept that trips people up most: **{concepts[0][0]}** — {concepts[0][1]}")
    reading = (
        "**Further reading**\n\n"
        f"- Official {topic} documentation for {module.lower()}\n"
        "- The linked FixitLab lab (deliberate break → fix → verify)\n"
        "- The next module in this course"
    )
    return (
        f"## Key takeaways\n\n"
        + "\n".join(f"- {b}" for b in bullets[:6])
        + "\n\n"
        + reading
    )


# Topic fallback commands so EVERY module shows real syntax even when a topic
# profile has no curated `commands` map. Keyed by a lowercase substring of the
# course topic. (lang, {section_key: command}).
_FALLBACK_CMDS: dict[str, tuple[str, dict[str, str]]] = {
    "linux": ("bash", {
        "labs": "id; whoami\nsystemctl status sshd\njournalctl -xe | tail -20",
    }),
    "rhel": ("bash", {
        "labs": "subscription-manager status\ndnf repolist\nsystemctl status firewalld",
    }),
    "docker": ("bash", {
        "labs": "docker ps -a\ndocker run -d -p 8080:80 --name web nginx\ndocker logs web",
    }),
    "kubernetes": ("bash", {
        "labs": "kubectl get pods -A\nkubectl describe pod <pod>\nkubectl apply -f manifest.yaml",
    }),
    "terraform": ("hcl", {
        "labs": "terraform init\nterraform plan -out=tfplan\nterraform apply tfplan",
    }),
    "ansible": ("yaml", {
        "labs": "ansible -m ping all\nansible-playbook site.yml --check --diff\nansible-playbook site.yml",
    }),
    "python": ("python", {
        "labs": "python -m venv .venv && source .venv/bin/activate\npip install -r requirements.txt\npython -m pytest -q",
    }),
    "git": ("bash", {
        "labs": "git status\ngit checkout -b feature/x\ngit add -p && git commit -m 'msg'",
    }),
    "sql": ("sql", {
        "labs": "SELECT version();\nEXPLAIN ANALYZE SELECT * FROM orders WHERE id = 1;",
    }),
    "prometheus": ("promql", {
        "labs": "up\nrate(http_requests_total[5m])",
    }),
    "grafana": ("bash", {
        "labs": "curl -s http://localhost:3000/api/health\ncurl -s http://localhost:3000/api/datasources",
    }),
}


def _fallback_for(topic: str) -> tuple[str, dict[str, str]] | None:
    t = (topic or "").lower()
    for key, val in _FALLBACK_CMDS.items():
        if key in t:
            return val
    return None


def _build_code(section_key: str, topic: str, module: str, profile: dict) -> tuple[str, str, str]:
    """Section-level code block (rendered in the dedicated code pane).

    Only the walkthrough carries a code block now — the shell command sequence
    for the module. Keeping this on the model field (not just in-body) preserves
    the ShellBlock output-pane rendering the frontend expects.
    """
    if section_key != "walkthrough":
        return "", "text", ""
    cmds = profile.get("commands") or {}
    fb = _fallback_for(topic)
    if cmds:
        key = next(iter(cmds))
        code = cmds[key] if isinstance(cmds[key], str) else str(cmds[key])
        return f"# {module}\n{code}", "bash", f"{topic} hands-on — run in playground"
    if fb and fb[1].get("labs"):
        return f"# {module}\n{fb[1]['labs']}", fb[0], f"{topic} hands-on — run in playground"
    return "", "text", ""


def build_rich_module_sections(
    course: dict, module_title: str, level: str
) -> list[tuple[str, str, str, str, str]]:
    """Return the lean 6-section lesson for one course module.

    Each element is (heading, body, code, code_language, code_caption).
    """
    topic = course["topic"]
    playground = course.get("playground_slug") or topic.lower()
    course_slug = course.get("course_slug", "")
    scenario = course.get("scenario_slug", "")
    profile = get_profile(topic)

    sections: list[tuple[str, str, str, str, str]] = []
    for heading, key in SECTION_HEADINGS:
        if key == "overview":
            body = _write_overview(topic, module_title, level, profile, course_slug)
        elif key == "concepts":
            body = _write_concepts(topic, module_title, level, profile)
        elif key == "walkthrough":
            body = _write_walkthrough(topic, module_title, level, profile, playground)
        elif key == "pitfalls":
            body = _write_pitfalls(topic, module_title, level, profile, course_slug)
        elif key == "assess":
            body = _write_assess(topic, module_title, level, profile, playground, scenario)
        else:  # takeaways
            body = _write_takeaways(topic, module_title, level, profile)
        code, lang, caption = _build_code(key, topic, module_title, profile)
        sections.append((heading, body, code, lang, caption))
    return sections
