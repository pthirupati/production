"""
Lean, high-signal tutorial section writers — six sections per module.

Redesigned (2026-07) from the old 20-section structure to a concise, non-repetitive
lesson that reads in a few minutes, then re-upgraded (2026-07) for CLARITY so a
generated lesson stands next to TutorialsPoint / a good Medium post:

    1. Overview                 — plain-language "what/why" + analogy + ONE diagram (Learn)
    2. Key concepts             — module-specific concepts + a real comparison table (Learn)
    3. Hands-on walkthrough     — a narrated, step-by-step worked example with REAL
                                  commands + expected output + ONE sequenceDiagram      (Practice)
    4. Common pitfalls & fixes  — real failure modes with the actual error text + fix   (Operate)
    5. Practice & assess        — linked-lab CTA + a quick-reference cheat sheet + quiz (Assess)
    6. Key takeaways            — 4-6 bullets + further reading                          (Assess)

Quality bar (what "good" means here — used to judge before/after):
    * Concrete, not templated: named resources (``web-1``, not ``POD``); a real
      command shows real output; every claim is checkable.
    * Plain-language first: one analogy + one "why it matters" line per lesson so a
      newcomer has a hook before the jargon.
    * Skimmable: short paragraphs, numbered steps, bold leads, callouts.
    * Topic-specific: a Kubernetes lesson shows kubectl output; a Linux one shows a
      real shell session; a Terraform one shows a real plan diff.
    * Actionable failure modes: the symptom, the *literal* error string, then the fix.

De-duplication guarantee (unchanged): exactly ONE architecture (flowchart) diagram in
Overview and exactly ONE sequenceDiagram in the walkthrough — no diagram is repeated in
any other section.

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


def _topic_key(topic: str, course_slug: str = "") -> str:
    """Return the coarse topic bucket used by the content tables below.

    Matches on a substring of ``course_slug`` + ``topic`` so PostgreSQL/MySQL land
    on ``database``, OpenShift lands on ``kubernetes``, etc.
    """
    hay = f"{course_slug} {topic}".lower()
    # Order matters: most specific first.
    buckets = [
        ("kubernetes", ("kubernetes", "k8s", "openshift", "helm", "kubectl")),
        ("docker", ("docker", "podman", "containerd", "container")),
        ("terraform", ("terraform", "pulumi", "cloudformation", "packer")),
        ("ansible", ("ansible", "awx", "tower")),
        ("aws", ("aws", "amazon web", " ec2", " s3", "iam")),
        ("database", ("database", "postgres", "postgre", "mysql", "sqlite", "mongo", "redis", "sql")),
        ("git", ("git", "github", "gitlab", "version control")),
        ("networking", ("network", "tcp", "dns", "routing", "vyos", "bgp")),
        ("security", ("security", "cyber", "siem", "hardening", "devsecops")),
        ("monitoring", ("monitor", "prometheus", "grafana", "observab", "sre")),
        ("vmware", ("vmware", "vsphere", "esxi", "vcenter")),
        ("windows", ("windows", "active directory", "powershell")),
        ("python", ("python", "fastapi", "flask", "django")),
        ("shell", ("bash", "shell", "scripting")),
        ("linux", ("linux", "rhel", "ubuntu", "centos", "systemd")),
    ]
    for key, needles in buckets:
        if any(n in hay for n in needles):
            return key
    return ""


def _match_concepts(profile: dict, module: str, topic: str = "", course_slug: str = "") -> list[tuple[str, str]]:
    """Return (name, description) concept pairs most relevant to THIS module.

    Prefers concepts whose key overlaps the module title, then a module-keyword
    fallback table (so a "Users, groups & permissions" module gets user/group
    concepts, not the profile's first-four), then the first few profile concepts.
    """
    concepts = profile.get("concepts") or {}
    keys = _kw(module)
    matched: list[tuple[str, str]] = []
    for key, text in concepts.items():
        parts = set(key.lower().replace("_", " ").split())
        if keys & parts or any(p in module.lower() for p in parts):
            matched.append((key.replace("_", " ").title(), text))

    # Module-keyword fallback — concepts chosen from the module title, not the
    # topic. Merge with any profile matches so a single profile hit (e.g. "Pod")
    # is still fleshed out to 3-4 module-relevant concepts, deduped by name.
    mod_fb = _module_concepts(module, topic, course_slug)
    if mod_fb:
        seen = {n.lower() for n, _ in matched}
        for name, desc in mod_fb:
            if name.lower() not in seen:
                matched.append((name, desc))
                seen.add(name.lower())
    if matched:
        return matched[:5]

    if concepts:
        return [(k.replace("_", " ").title(), v) for k, v in list(concepts.items())[:4]]
    return []


# ── Module-keyword concept fallback ────────────────────────────────────────
# When neither the module title nor the topic profile yields concepts, pick a
# module-relevant set from the words in the module title. Keyed by a substring
# match against the (lowercased) module title. Concrete, one-sentence definitions.

_MODULE_CONCEPTS: list[tuple[tuple[str, ...], list[tuple[str, str]]]] = [
    (("user", "group", "account", "permission", "sudo"), [
        ("Users & UIDs", "Every login maps to a numeric UID in `/etc/passwd`; UID 0 is root. `id <user>` shows the mapping."),
        ("Groups & GIDs", "A group bundles users so you grant a permission once (`/etc/group`); primary vs supplementary groups matter for new files."),
        ("File mode (rwx)", "Read/write/execute for owner/group/other — `chmod 640 file` means owner rw, group r, other none."),
        ("sudo / least privilege", "Grant specific commands via `/etc/sudoers.d/`, never blanket root; every `sudo` use is logged."),
    ]),
    (("permission", "chmod", "chown", "acl"), [
        ("Octal mode", "`chmod 755` = rwxr-xr-x. The digits are owner/group/other; add 4=r, 2=w, 1=x."),
        ("Ownership", "`chown user:group file` sets who owns it; you usually need root to give a file away."),
        ("The directory `x` bit", "Execute on a directory means *traverse*; without it you can't `cd` in even if you can read the listing."),
        ("ACLs", "`setfacl -m u:alice:rwx file` grants extra users access beyond the single owner/group model."),
    ]),
    (("pod", "deployment", "replicaset", "workload"), [
        ("Pod", "The smallest deployable unit — one or more containers sharing an IP and lifecycle; ephemeral by design."),
        ("ReplicaSet", "Keeps N identical Pods running; you rarely touch it directly — a Deployment manages it for you."),
        ("Deployment", "Declarative desired state for Pods; rolling updates via `maxSurge`/`maxUnavailable`, rollback with one command."),
        ("Label & selector", "Free-form key/value tags; Services and controllers find Pods by matching labels — a typo here silently breaks routing."),
    ]),
    (("service", "ingress", "network", "dns", "cni"), [
        ("Service", "A stable virtual IP + DNS name in front of a changing set of Pods (ClusterIP internal, LoadBalancer external)."),
        ("Endpoints", "The live list of ready Pod IPs behind a Service — empty Endpoints = a broken selector or failing readiness probe."),
        ("Ingress", "L7 (HTTP) routing by host/path into Services, terminated by an Ingress controller (nginx/traefik)."),
        ("Readiness probe", "Gates whether a Pod joins its Service; a failing probe removes the Pod from traffic without killing it."),
    ]),
    (("image", "build", "dockerfile", "layer", "registry"), [
        ("Image", "A read-only, layered filesystem + metadata; each Dockerfile instruction adds a cache-able layer."),
        ("Layer cache", "Docker reuses unchanged layers — order your Dockerfile so dependencies install *before* you copy source."),
        ("Tag", "A human name for an image digest (`nginx:1.27`); `latest` is a moving target, pin real versions in prod."),
        ("Registry", "Where images live (`docker push`/`pull`); private registries need an auth secret to pull."),
    ]),
    (("volume", "storage", "persist", "pvc", "mount"), [
        ("Ephemeral layer", "A container's writable layer dies with the container — never store data you care about there."),
        ("Named volume", "Managed storage that outlives the container (`-v data:/var/lib/...`); the safe place for state."),
        ("Bind mount", "Maps a host path into the container — great for dev, surprising in prod (host permissions leak in)."),
        ("PersistentVolumeClaim", "In Kubernetes, a Pod's request for durable storage; stuck `Pending` usually means no matching StorageClass."),
    ]),
    (("state", "backend", "plan", "apply"), [
        ("State file", "Terraform's map from your config addresses to real cloud resource IDs — the source of truth, treat it as sensitive."),
        ("Plan", "A dry-run diff (create/change/destroy) you read *before* apply; no surprises if you always plan first."),
        ("Remote backend + lock", "Store state in S3/TFC with locking so two `apply`s can't corrupt it — never share a local `.tfstate`."),
        ("Resource address", "`aws_instance.web` — Terraform keys on this, not the cloud name, so renaming forces a destroy/recreate unless you `state mv`."),
    ]),
    (("index", "query", "explain", "performance"), [
        ("Index", "A sorted lookup structure (usually B-tree) that turns a full table scan into a fast seek — but slows writes."),
        ("Query plan", "`EXPLAIN (ANALYZE, BUFFERS)` shows how the DB will run a query; `Seq Scan` on a big table is your red flag."),
        ("Statistics", "The planner guesses row counts from stats; stale stats cause bad plans — `ANALYZE` refreshes them."),
        ("Covering index", "An index that contains every column a query needs, so the DB never touches the table (`Index Only Scan`)."),
    ]),
    (("backup", "restore", "replication", "recovery"), [
        ("Logical backup", "`pg_dump`/`mysqldump` — portable SQL, slow to restore, survives version bumps."),
        ("Physical backup + PITR", "Base backup + WAL/binlog lets you restore to an exact moment; fast for large DBs."),
        ("Replication lag", "Seconds the replica trails the primary; watch it — a lagging replica serves stale reads."),
        ("Tested restore", "A backup you have never restored is a hope, not a recovery plan — rehearse it on a schedule."),
    ]),
    (("branch", "merge", "commit", "rebase"), [
        ("Commit", "An immutable snapshot + parent pointer; the SHA is the id you can always return to via `git reflog`."),
        ("Branch", "Just a movable pointer to a commit — cheap to create, the unit of parallel work."),
        ("Merge vs rebase", "Merge preserves history with a merge commit; rebase rewrites your commits onto a new base for a linear log."),
        ("Remote tracking", "`origin/main` is your last-known copy of the remote; `fetch` updates it, `pull` = fetch + merge."),
    ]),
]


def _module_concepts(module: str, topic: str = "", course_slug: str = "") -> list[tuple[str, str]]:
    m = (module or "").lower()
    for needles, items in _MODULE_CONCEPTS:
        if any(n in m for n in needles):
            return items
    return []


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


# ── Plain-language framing: analogy + "why it matters" ──────────────────────
# One hook per topic so a newcomer has a mental model before the jargon. Keyed by
# the coarse bucket from _topic_key(); falls back to a generic (still useful) line.

_ANALOGY: dict[str, str] = {
    "linux": "Think of a Linux box like an office building: **users** are people with badges, **groups** are teams, **file permissions** are which doors each badge opens, and **systemd** is the facilities manager that starts and restarts the services.",
    "kubernetes": "Think of Kubernetes as an air-traffic controller for containers: you declare *\"I want 3 of these planes in the air\"* (a Deployment), and the controller keeps re-launching Pods until reality matches — rescheduling them when a runway (node) goes down.",
    "docker": "A Docker **image** is like a shipping container: packed once, it runs the same on your laptop, CI, and prod. The **container** is that box actually in transit; when it's unloaded (removed), anything you scribbled on the inside is gone unless you put it in a **volume**.",
    "terraform": "Terraform is a blueprint you `apply` to reality. The **state file** is the as-built record that ties every line of your blueprint to a real wall in the building — lose it or edit it by hand and Terraform no longer knows what it already built.",
    "ansible": "Ansible is a checklist you hand to every server at once: each task says *\"make sure nginx is installed\"* (a desired state), not *\"run this install command\"* — so re-running the play is safe and only changes what drifted.",
    "aws": "AWS is a data center you rent by the API call. A running EC2 instance you can't reach is almost always a locked door somewhere on the path — security group, route table, or subnet — not a broken server.",
    "database": "A database index is the alphabetical thumb-tabs on a dictionary: without them the engine reads every page (a `Seq Scan`); with the right one it jumps straight to the entry. Too many tabs, though, and every edit has to update them all.",
    "git": "Git history is a chain of save-points. A **commit** is a labelled snapshot, a **branch** is just a sticky note pointing at one of them, and `git reflog` is the security-camera footage proving nothing you committed is ever truly lost.",
    "networking": "A packet's journey is like posting a letter: DNS is the address book, the routing table is the sorting office deciding the next hop, and a firewall is the mail room that may quietly bin letters to certain doors (ports).",
    "security": "Security is a series of locked doors, not a single wall. **Least privilege** means each key opens only the rooms it must; when one key leaks, the blast radius is one room — not the whole building.",
    "monitoring": "Monitoring is the dashboard of a car. **Metrics** are the gauges (speed, fuel), **logs** are the trip diary of what happened, and **traces** show the exact route a single request took — you need all three to know *why* you're slow, not just *that* you are.",
    "vmware": "A hypervisor is a landlord subdividing one physical building (the host) into apartments (VMs). **%CPU Ready** is a tenant waiting in the lobby for an elevator (a physical core) — the apartment looks idle but can't get anywhere.",
    "windows": "Active Directory is the company HR directory: it decides who you are (authentication) and what you may open (authorization). Kerberos, its ID-check, refuses badges whose clock is more than five minutes off.",
    "python": "A virtual environment is a clean workbench per project: `.venv` keeps each project's tools separate so upgrading one project can't snap another. `which python` tells you which bench you're actually standing at.",
    "shell": "A shell script is a recipe the computer follows literally — it will happily cook a disaster if you don't quote your ingredients. `set -euo pipefail` is the smoke alarm that stops cooking the moment a step fails.",
}

_WHY: dict[str, str] = {
    "linux": "Almost every server, container, and cloud VM you'll ever touch is Linux — get comfortable here and the rest of the stack stops being mysterious.",
    "kubernetes": "Kubernetes is how modern teams run services that heal themselves and scale on demand; the failure modes here (Pending, CrashLoop, 503) are the ones you'll actually be paged for.",
    "docker": "Containers are the unit of deployment everywhere now — if you can build a small, reproducible image, your app runs the same in every environment and 'works on my machine' stops being an excuse.",
    "terraform": "Clicking in a cloud console doesn't scale and can't be reviewed; codified infrastructure can be planned, peer-reviewed, and rolled back — this is what 'infrastructure as code' buys you.",
    "ansible": "Manual server setup drifts and can't be repeated; idempotent automation means your 500th server is configured exactly like your first, and a rebuild is a command, not a memory test.",
    "aws": "The cloud bill and the 2 a.m. page both come from the same misunderstandings — knowing the real path a request (and a dollar) takes is what separates 'it works' from 'it works, securely, at cost'.",
    "database": "The database is usually the hardest thing to scale and the easiest thing to lose data in; understanding indexes, plans, and backups is the difference between a fast app and a 3 a.m. incident.",
    "git": "Every team runs on Git, and the scary moments (wrong branch, bad merge, committed secret) are recoverable *if* you understand the model — panic is just not knowing `reflog` exists.",
    "networking": "When something 'can't connect', the fault is almost never the app — it's a layer of the network path. Knowing where to look turns an hour of guessing into a two-command diagnosis.",
    "security": "One over-broad permission or leaked secret is how most breaches actually start; building least-privilege habits now is cheaper than an incident later.",
    "monitoring": "You can't fix what you can't see, and you'll drown in alerts you can't act on — good observability is what lets you sleep through the night *and* find the root cause fast when you can't.",
    "vmware": "Virtualization runs a huge share of enterprise workloads; the classic traps (snapshot sprawl, CPU Ready, orphaned locks) quietly degrade performance long before anything obviously breaks.",
    "windows": "Enterprise identity, file shares, and much of corporate IT still runs on Windows and Active Directory — the auth and GPO gotchas here block real users daily.",
    "python": "Python is the glue of automation, data, and APIs; the environment and dependency traps are the #1 reason 'it worked yesterday' — master them and you stop fighting your tools.",
    "shell": "The shell is the lowest common denominator on every server; a robust script saves hours of repeated toil, and one unquoted variable is how a script deletes the wrong thing.",
}


def _analogy_for(topic: str, course_slug: str = "") -> str:
    return _ANALOGY.get(_topic_key(topic, course_slug), "")


def _why_for(topic: str, course_slug: str = "") -> str:
    return _WHY.get(
        _topic_key(topic, course_slug),
        f"Getting {topic} right is what keeps the systems that depend on it fast, reversible, and observable.",
    )


# ── Topic-specific worked examples ──────────────────────────────────────────
# A narrated, concrete, step-by-step hands-on walkthrough with REAL commands and
# realistic output. This is the biggest clarity win: named resources (web-1, not
# POD), a story ("first inspect, then change one thing, then verify"), and the
# exact output to compare against. Keyed by the coarse topic bucket.
#
# Each entry is a list of steps; a step is (narration, command, expected_output).
# ``command`` may be multi-line (fed verbatim into the ```bash block). ``expected_output``
# is the sample the learner compares against ("" = a command with no stdout).

_WORKED: dict[str, list[tuple[str, str, str]]] = {
    "linux": [
        ("First, see who you are and what you can touch — never change permissions blind.",
         "id deploy",
         "uid=1001(deploy) gid=1001(deploy) groups=1001(deploy),10(wheel)"),
        ("Look at the file whose access you're about to change. The `-l` long listing shows the mode and owner.",
         "ls -l /srv/app/config.yml",
         "-rw-r----- 1 root appgrp 812 Jul 15 09:20 /srv/app/config.yml"),
        ("`deploy` can't read it (not root, not in `appgrp`). Add the user to the group — one change.",
         "sudo usermod -aG appgrp deploy",
         ""),
        ("Group membership is only picked up on a new login. Verify it landed, then re-open a session.",
         "id deploy",
         "uid=1001(deploy) gid=1001(deploy) groups=1001(deploy),10(wheel),1200(appgrp)"),
        ("Now confirm the fix the same way you found the problem — read the file as `deploy`.",
         "sudo -u deploy cat /srv/app/config.yml | head -1",
         "listen_port: 8080"),
    ],
    "kubernetes": [
        ("Start with the symptom, not a guess. List Pods and read the STATUS column.",
         "kubectl get pods -n shop",
         "NAME                     READY   STATUS             RESTARTS   AGE\n"
         "web-6f4b9c8d7-2xk9p      0/1     CrashLoopBackOff   4          3m\n"
         "web-6f4b9c8d7-9qz2m      1/1     Running            0          3m"),
        ("`describe` shows the *why*: events at the bottom are the story of what the scheduler and kubelet did.",
         "kubectl describe pod web-6f4b9c8d7-2xk9p -n shop | tail -4",
         "  Warning  BackOff  12s (x5 over 2m)  kubelet  Back-off restarting failed container\n"
         "  Normal   Pulled   2m                kubelet  Successfully pulled image \"shop/web:1.4\""),
        ("The container starts then dies — read the *previous* attempt's logs, not the current empty one.",
         "kubectl logs web-6f4b9c8d7-2xk9p -n shop --previous | tail -2",
         "Error: DATABASE_URL is not set\n"
         "npm ERR! code 1"),
        ("Root cause found: a missing env var. Patch the Deployment (the Pod is managed, don't edit it directly).",
         "kubectl set env deployment/web -n shop DATABASE_URL=postgres://db:5432/shop",
         "deployment.apps/web env updated"),
        ("Watch the rollout replace the bad Pods. Verify the same way you started — every Pod READY 1/1.",
         "kubectl get pods -n shop",
         "NAME                     READY   STATUS    RESTARTS   AGE\n"
         "web-7c9d5f6b4-abcde      1/1     Running   0          20s\n"
         "web-7c9d5f6b4-fghij      1/1     Running   0          18s"),
    ],
    "docker": [
        ("The container you just started isn't there. List *all* containers, including exited ones.",
         "docker ps -a",
         "CONTAINER ID   IMAGE          STATUS                     PORTS   NAMES\n"
         "a1b2c3d4e5f6   shop/web:1.4   Exited (1) 8 seconds ago           web"),
        ("A container lives only as long as its PID 1. Read why it stopped.",
         "docker logs web",
         "node:internal/modules/cjs/loader: Cannot find module '/app/server.js'"),
        ("The image was built with the source in the wrong path. Inspect the layers to confirm what's inside.",
         "docker run --rm --entrypoint ls shop/web:1.4 /app",
         "package.json\nsrc"),
        ("Fix the Dockerfile's COPY, rebuild, then run it again — this time publish the port and keep it alive.",
         "docker build -t shop/web:1.5 . && docker run -d -p 8080:80 --name web shop/web:1.5",
         "Successfully tagged shop/web:1.5\n7f2c8e1a3b4d9e0f"),
        ("Verify it's actually serving, not just 'Up'. Curl the published port.",
         "curl -s -o /dev/null -w '%{http_code}\\n' localhost:8080",
         "200"),
    ],
    "terraform": [
        ("Never apply blind. Initialise providers, then produce a plan you can read and save.",
         "terraform init && terraform plan -out=tfplan",
         "Terraform will perform the following actions:\n\n"
         "  # aws_instance.web will be created\n"
         "  + resource \"aws_instance\" \"web\" {\n"
         "      + ami           = \"ami-0abc123\"\n"
         "      + instance_type = \"t3.micro\"\n"
         "    }\n\n"
         "Plan: 1 to add, 0 to change, 0 to destroy."),
        ("The plan says *add 1* — exactly what you expect. Apply the saved plan so nothing can drift between plan and apply.",
         "terraform apply tfplan",
         "aws_instance.web: Creating...\n"
         "aws_instance.web: Creation complete after 22s [id=i-0abc123def456]\n\n"
         "Apply complete! Resources: 1 added, 0 changed, 0 destroyed."),
        ("Now you rename the resource in code. A naive plan wants to DESTROY and RE-CREATE it — data loss.",
         "terraform plan",
         "Plan: 1 to add, 0 to change, 1 to destroy."),
        ("Tell Terraform it's the same object, not a new one, with a `moved` block (or `state mv`).",
         "terraform state mv aws_instance.web aws_instance.frontend",
         "Move \"aws_instance.web\" to \"aws_instance.frontend\"\nSuccessful move."),
        ("Re-plan to prove the rename is now a no-op — the safest possible change.",
         "terraform plan",
         "No changes. Your infrastructure matches the configuration."),
    ],
    "ansible": [
        ("Before any play, confirm the control node can actually reach the hosts over SSH.",
         "ansible web -m ping",
         "web-01 | SUCCESS => {\n    \"changed\": false,\n    \"ping\": \"pong\"\n}\n"
         "web-02 | SUCCESS => {\n    \"changed\": false,\n    \"ping\": \"pong\"\n}"),
        ("Dry-run the play with `--check --diff` — see what *would* change without touching anything.",
         "ansible-playbook site.yml --check --diff",
         "TASK [nginx : install package] *************************************\n"
         "changed: [web-01]\n\n"
         "PLAY RECAP *********************************************************\n"
         "web-01  : ok=4    changed=1    unreachable=0    failed=0"),
        ("The diff looked right — run it for real. Idempotent modules only change what drifted.",
         "ansible-playbook site.yml",
         "PLAY RECAP *********************************************************\n"
         "web-01  : ok=4    changed=1    unreachable=0    failed=0\n"
         "web-02  : ok=4    changed=1    unreachable=0    failed=0"),
        ("Prove idempotency: run it AGAIN. A well-written play now reports `changed=0`.",
         "ansible-playbook site.yml",
         "PLAY RECAP *********************************************************\n"
         "web-01  : ok=4    changed=0    unreachable=0    failed=0\n"
         "web-02  : ok=4    changed=0    unreachable=0    failed=0"),
    ],
    "aws": [
        ("Always confirm which identity you're operating as before you touch anything.",
         "aws sts get-caller-identity",
         "{\n    \"Account\": \"123456789012\",\n"
         "    \"Arn\": \"arn:aws:iam::123456789012:role/deployer\"\n}"),
        ("The instance is 'running' but SSH hangs. Work the path outward — check its security group ingress.",
         "aws ec2 describe-security-groups --group-ids sg-0abc --query 'SecurityGroups[0].IpPermissions'",
         "[]"),
        ("Empty ingress — nothing can reach it. Open port 22 to *your* IP only (never 0.0.0.0/0).",
         "aws ec2 authorize-security-group-ingress --group-id sg-0abc \\\n"
         "  --protocol tcp --port 22 --cidr 203.0.113.5/32",
         "{\n    \"Return\": true\n}"),
        ("Confirm the rule is in place, then the SSH handshake should complete.",
         "aws ec2 describe-security-groups --group-ids sg-0abc \\\n"
         "  --query 'SecurityGroups[0].IpPermissions[0].FromPort'",
         "22"),
    ],
    "database": [
        ("A report query got slow. Ask the planner how it will run it — don't guess.",
         "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE customer_id = 42;",
         "Seq Scan on orders  (cost=0.00..21520.00 rows=1 width=64)\n"
         "  Filter: (customer_id = 42)\n"
         "  Rows Removed by Filter: 999999\n"
         "Execution Time: 412.880 ms"),
        ("`Seq Scan` reading a million rows for one customer = a missing index. Add one on the filter column.",
         "CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer_id);",
         "CREATE INDEX"),
        ("Refresh planner statistics so it knows the new index is worth using.",
         "ANALYZE orders;",
         "ANALYZE"),
        ("Re-run the exact same EXPLAIN — the plan should flip to an Index Scan and drop from ~400ms to sub-ms.",
         "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE customer_id = 42;",
         "Index Scan using idx_orders_customer on orders  (cost=0.42..8.44 rows=1 width=64)\n"
         "  Index Cond: (customer_id = 42)\n"
         "Execution Time: 0.061 ms"),
    ],
    "git": [
        ("You committed to the wrong branch. First, breathe — see exactly where you are.",
         "git status && git log --oneline -1",
         "On branch main\n"
         "nothing to commit, working tree clean\n"
         "a1b2c3d Add password reset endpoint"),
        ("Create the branch the work *should* be on — it now points at your commit.",
         "git branch feature/pw-reset",
         ""),
        ("Move `main` back one commit so it no longer carries your change. `--soft` keeps files untouched.",
         "git reset --hard origin/main",
         "HEAD is now at 9f8e7d6 Merge pull request #212"),
        ("Switch to the feature branch — your commit is safely here.",
         "git switch feature/pw-reset && git log --oneline -1",
         "Switched to branch 'feature/pw-reset'\n"
         "a1b2c3d Add password reset endpoint"),
        ("Worried you lost anything? `reflog` is the safety net — every HEAD you've been on is recoverable.",
         "git reflog -3",
         "a1b2c3d HEAD@{0}: checkout: moving to feature/pw-reset\n"
         "9f8e7d6 HEAD@{1}: reset: moving to origin/main\n"
         "a1b2c3d HEAD@{2}: commit: Add password reset endpoint"),
    ],
    "networking": [
        ("`ping` succeeds but the app won't connect. Confirm reachability is a red herring — ICMP is L3.",
         "ping -c 2 api.internal",
         "PING api.internal (10.0.2.20) 56(84) bytes of data.\n"
         "64 bytes from 10.0.2.20: icmp_seq=1 ttl=63 time=0.9 ms\n"
         "64 bytes from 10.0.2.20: icmp_seq=2 ttl=63 time=0.8 ms"),
        ("Test the *actual* service port instead. `nc -vz` opens a TCP connection and reports pass/fail.",
         "nc -vz api.internal 8443",
         "nc: connect to api.internal port 8443 (tcp) failed: Connection refused"),
        ("Refused, not timed out — something answered. Check whether the service is even listening on that port.",
         "ss -tlnp | grep 8443",
         ""),
        ("Nothing is listening. The app bound to the wrong port; fix the config and confirm it now listens.",
         "ss -tlnp | grep 8443",
         "LISTEN 0  128  0.0.0.0:8443  0.0.0.0:*  users:((\"api\",pid=2210,fd=6))"),
    ],
    "monitoring": [
        ("A dashboard is green but users report errors. Query the raw target health first.",
         "up{job=\"api\"}",
         "up{job=\"api\", instance=\"10.0.1.10:9100\"}  1\n"
         "up{job=\"api\", instance=\"10.0.1.11:9100\"}  1"),
        ("Targets are up — you're watching the wrong SLI. Measure user-facing errors, not host health.",
         "sum(rate(http_requests_total{job=\"api\",status=~\"5..\"}[5m]))",
         "{}  7.4"),
        ("7 errors/sec, invisible on a host-up panel. Compare against total to get an error ratio.",
         "sum(rate(http_requests_total{job=\"api\",status=~\"5..\"}[5m]))\n"
         "  / sum(rate(http_requests_total{job=\"api\"}[5m]))",
         "{}  0.031"),
        ("3.1% error rate — that's the alert you actually want, on symptoms not resources.",
         "histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))",
         "{}  1.85"),
    ],
    "vmware": [
        ("A VM feels slow but guest CPU looks idle. Inspect it — power state and tools first.",
         "govc vm.info web-prod-01",
         "Name:           web-prod-01\n"
         "  Power state:  poweredOn\n"
         "  Guest OS:     Ubuntu Linux (64-bit)\n"
         "  CPU:          8 vCPU"),
        ("Guest is idle but the *host* is contended. The real signal is %CPU Ready — time the VM waits for a core.",
         "esxtop  # press 'c', read the %RDY column for web-prod-01",
         "   NAME            %USED   %RDY   %CSTP\n"
         "   web-prod-01     4.10    38.20   0.00"),
        ("38% Ready = the VM spends a third of its time queued for physical cores. It's oversized for a busy host.",
         "govc vm.change -vm web-prod-01 -c 4",
         ""),
        ("Re-check %RDY after right-sizing — fewer vCPUs paradoxically makes an oversized VM faster.",
         "esxtop  # press 'c', re-read %RDY",
         "   NAME            %USED   %RDY   %CSTP\n"
         "   web-prod-01     6.80     4.10   0.00"),
    ],
    "windows": [
        ("A GPO change 'isn't applying'. Force a refresh instead of waiting for the background cycle.",
         "gpupdate /force",
         "Updating policy...\n\n"
         "Computer Policy update has completed successfully.\n"
         "User Policy update has completed successfully."),
        ("See which GPOs actually won — precedence and filtering decide, not just that a GPO exists.",
         "gpresult /r /scope:computer",
         "Applied Group Policy Objects\n"
         "    Default Domain Policy\n"
         "    Workstation Security Baseline"),
        ("Your GPO is missing from the applied list. AD auth issues are often clock skew — Kerberos allows only 5 min.",
         "w32tm /query /status | findstr Offset",
         "Phase Offset: 0.0012431s"),
        ("Clock is fine; the GPO was link-disabled. Re-enable the link, refresh, and confirm it now applies.",
         "gpresult /r /scope:computer | findstr /C:\"Workstation Security Baseline\"",
         "    Workstation Security Baseline"),
    ],
    "python": [
        ("`ModuleNotFoundError` after a pip install? First confirm *which* interpreter you're actually using.",
         "which python && python -V",
         "/usr/bin/python\nPython 3.12.3"),
        ("That's the system Python, not your project's. Create and activate an isolated environment.",
         "python -m venv .venv && source .venv/bin/activate",
         ""),
        ("Now `which python` points inside the project. Install pinned dependencies into it.",
         "which python && pip install -r requirements.txt",
         "/home/dev/app/.venv/bin/python\n"
         "Successfully installed requests-2.32.3 httpx-0.27.0"),
        ("The import that failed now resolves — because you're finally running the right interpreter.",
         "python -c 'import requests; print(requests.__version__)'",
         "2.32.3"),
    ],
    "shell": [
        ("A script silently did the wrong thing on a filename with spaces. Reproduce it, then harden it.",
         "cat backup.sh",
         "#!/usr/bin/env bash\nfor f in $FILES; do rm $f; done"),
        ("Two bugs: unquoted `$FILES` word-splits, and no fail-fast. Let shellcheck confirm before you touch it.",
         "shellcheck backup.sh",
         "In backup.sh line 2:\n"
         "for f in $FILES; do rm $f; done\n"
         "         ^-- SC2086: Double quote to prevent globbing and word splitting."),
        ("Add strict mode and quote every expansion — the two lines that prevent most shell disasters.",
         "head -2 backup.sh",
         "#!/usr/bin/env bash\nset -euo pipefail"),
        ("Re-run shellcheck: clean. A syntax check (`bash -n`) confirms it parses before it ever runs.",
         "shellcheck backup.sh && bash -n backup.sh && echo OK",
         "OK"),
    ],
}


def _worked_for(topic: str, course_slug: str = "") -> list[tuple[str, str, str]]:
    return _WORKED.get(_topic_key(topic, course_slug), [])


def _generic_worked(topic: str, module: str, profile: dict) -> list[tuple[str, str, str]]:
    """A realistic inspect → change → verify example for topics without a curated
    worked example, built from the profile's own commands where possible.

    Guarantees a ``$``-prefixed command with sample output (so the shell block
    always carries expected output) even when the topic profile is synthesized.
    """
    from apps.tutorials.course_diagrams import sample_output_for

    cmds: list[str] = []
    profile_cmds = profile.get("commands") or {}
    for v in profile_cmds.values():
        for line in str(v).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                cmds.append(line.split("&&")[0].strip())
    fb = _fallback_for(topic)
    if fb:
        for line in fb[1].get("labs", "").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line not in cmds:
                cmds.append(line)

    steps: list[tuple[str, str, str]] = []
    narrations = [
        "Inspect first — capture the current state as your baseline before touching anything.",
        "Read the detail so you understand *why* the state is what it is.",
        "Make one small, reversible change that targets the symptom.",
        "Verify — re-run the inspection and diff against your baseline.",
    ]
    for i, cmd in enumerate(cmds[:4]):
        out = sample_output_for(cmd) or ""
        steps.append((narrations[min(i, len(narrations) - 1)], cmd, out))

    if not steps or not any(out for _n, _c, out in steps):
        # Last-resort, but still real and self-consistent: a health probe that
        # actually prints something, so the block carries expected output.
        svc = re.sub(r"[^a-z0-9-]+", "-", (topic or "service").lower()).strip("-") or "service"
        steps = [
            ("Inspect first — check the component is up and capture the baseline.",
             f"curl -sf http://localhost/health || systemctl is-active {svc}",
             "active"),
            ("Read the recent logs to understand current behaviour.",
             f"journalctl -u {svc} -n 5 --no-pager",
             f"{svc}[1123]: ready — listening on :8080\n{svc}[1123]: config loaded from /etc/{svc}/config.yml"),
            ("Verify after a change — the same probe should still report healthy.",
             f"curl -sf http://localhost/health || systemctl is-active {svc}",
             "active"),
        ]
    return steps


# ── Quick-reference cheat sheets ────────────────────────────────────────────
# A compact "commands you'll actually reach for" table, per topic. Rendered in
# Practice & assess so a learner can copy/paste under incident pressure. Rows are
# (task, command). Kept short and real.

_CHEATSHEET: dict[str, list[tuple[str, str]]] = {
    "linux": [
        ("Who am I / groups", "`id`"),
        ("Service state + why", "`systemctl status svc` · `journalctl -u svc -b`"),
        ("Permissions of a file", "`ls -l file` · `stat file`"),
        ("Fix mode / owner", "`chmod 640 file` · `chown user:grp file`"),
        ("Add user to group", "`usermod -aG grp user` (re-login to apply)"),
        ("Disk vs inodes", "`df -h` · `df -i`"),
    ],
    "kubernetes": [
        ("List / find bad Pods", "`kubectl get pods -A`"),
        ("Why is it broken", "`kubectl describe pod <p>`"),
        ("Crash logs", "`kubectl logs <p> --previous`"),
        ("Roll out a change", "`kubectl set env deploy/<d> K=V`"),
        ("Check routing", "`kubectl get endpoints <svc>`"),
        ("Wrong cluster?", "`kubectl config current-context`"),
    ],
    "docker": [
        ("All containers", "`docker ps -a`"),
        ("Why it exited", "`docker logs <c>`"),
        ("Peek inside image", "`docker run --rm --entrypoint ls <img> /app`"),
        ("Persist data", "`docker run -v data:/var/lib/...`"),
        ("Free space", "`docker system df` · `docker system prune`"),
    ],
    "terraform": [
        ("Preview change", "`terraform plan -out=tfplan`"),
        ("Apply saved plan", "`terraform apply tfplan`"),
        ("Rename, don't recreate", "`terraform state mv A B`"),
        ("What's managed", "`terraform state list`"),
        ("Ignore false drift", "`lifecycle { ignore_changes = [...] }`"),
    ],
    "ansible": [
        ("Can I reach hosts", "`ansible all -m ping`"),
        ("Dry run + diff", "`ansible-playbook site.yml --check --diff`"),
        ("Run for real", "`ansible-playbook site.yml`"),
        ("Escalate privilege", "`--become` / `become: true`"),
        ("Debug a variable", "`- debug: var=myvar`"),
    ],
    "aws": [
        ("Who am I", "`aws sts get-caller-identity`"),
        ("Instance state", "`aws ec2 describe-instances`"),
        ("Open a port (to your IP)", "`aws ec2 authorize-security-group-ingress`"),
        ("Why AccessDenied", "IAM Policy Simulator (SCP/boundary wins)"),
        ("Bucket visibility", "`aws s3 ls` · check Block Public Access"),
    ],
    "database": [
        ("How will it run", "`EXPLAIN (ANALYZE, BUFFERS) <query>`"),
        ("Add index (no lock)", "`CREATE INDEX CONCURRENTLY ...`"),
        ("Refresh stats", "`ANALYZE <table>`"),
        ("Who's connected", "`SELECT * FROM pg_stat_activity`"),
        ("Replica lag", "`SELECT * FROM pg_stat_replication`"),
    ],
    "git": [
        ("Where am I", "`git status` · `git log --oneline -5`"),
        ("Move work to a branch", "`git switch -c feature/x`"),
        ("Undo last commit (keep files)", "`git reset --soft HEAD~1`"),
        ("Recover 'lost' work", "`git reflog`"),
        ("Abort a bad merge", "`git merge --abort`"),
    ],
    "networking": [
        ("L3 reachability", "`ping -c 2 host`"),
        ("L4 port open?", "`nc -vz host port`"),
        ("Who's listening", "`ss -tlnp`"),
        ("DNS truth", "`dig @ns host`"),
        ("Which route wins", "`ip route get <dst>`"),
    ],
    "monitoring": [
        ("Target health", "`up`"),
        ("Error rate (SLI)", "`rate(http_requests_total{status=~\"5..\"}[5m])`"),
        ("p99 latency", "`histogram_quantile(0.99, ...)`"),
        ("Reduce cardinality", "`sum by (job) (...)`"),
        ("Alert on symptoms", "burn-rate on an SLO, not host CPU"),
    ],
    "vmware": [
        ("VM info", "`govc vm.info <vm>`"),
        ("CPU contention", "`esxtop` → %RDY column"),
        ("Right-size vCPU", "`govc vm.change -vm <vm> -c N`"),
        ("Snapshot cleanup", "consolidate/delete promptly"),
        ("Storage latency", "`esxtop` → DAVG/KAVG"),
    ],
    "windows": [
        ("Force policy", "`gpupdate /force`"),
        ("Which GPO won", "`gpresult /r`"),
        ("Clock skew (Kerberos)", "`w32tm /query /status`"),
        ("Service failure", "Event Viewer → System log"),
        ("Port test", "`Test-NetConnection host -Port 443`"),
    ],
    "python": [
        ("Which interpreter", "`which python && python -V`"),
        ("Isolate deps", "`python -m venv .venv && source .venv/bin/activate`"),
        ("Install pinned", "`pip install -r requirements.txt`"),
        ("List installed", "`python -m pip list`"),
        ("Run tests", "`python -m pytest -q`"),
    ],
    "shell": [
        ("Fail fast", "`set -euo pipefail`"),
        ("Always quote", "`\"$var\"` · `\"$@\"`"),
        ("Lint", "`shellcheck script.sh`"),
        ("Syntax check", "`bash -n script.sh`"),
        ("Trace execution", "`bash -x script.sh`"),
    ],
}


def _cheatsheet_for(topic: str, course_slug: str = "") -> list[tuple[str, str]]:
    return _CHEATSHEET.get(_topic_key(topic, course_slug), [])


# ── Topic-specific pitfalls ────────────────────────────────────────────────
# Real failure modes + the fix, keyed by a slugified topic (matched by substring
# so "PostgreSQL"/"MySQL" hit the database entry, etc.). Each pitfall is
# (symptom, fix). Concrete and topic-specific — this is a highest-value section.
# Where a literal error string exists, it is quoted so the reader can pattern-match.

_PITFALLS: dict[str, list[tuple[str, str]]] = {
    "linux": [
        ("A service won't start and `systemctl status` only says `Active: failed (Result: exit-code)`.",
         "Read the real error with `journalctl -u <svc> -b --no-pager`; a bad config path or missing user is almost always in the last 10 lines."),
        ("`bash: cd: /srv/app: Permission denied` even though the file mode looks right.",
         "Check the *directory* execute bit and SELinux context (`ls -Zld`, `getenforce`). A denied AVC won't show in `ls -l` — use `ausearch -m avc -ts recent`."),
        ("Writes fail with `No space left on device` but `df -h` shows free space.",
         "You've run out of inodes, not blocks. Confirm with `df -i` (IUse% at 100%) and clean up the directory full of millions of tiny files."),
        ("Editing `/etc/fstab` wrong drops you to `emergency mode` on reboot.",
         "Always add `nofail` to non-critical mounts and validate with `mount -a` (no errors) BEFORE rebooting."),
    ],
    "kubernetes": [
        ("Pod stuck in `Pending` forever.",
         "`kubectl describe pod` and read Events: `0/3 nodes are available: 3 Insufficient cpu` (raise/lower requests), a missing toleration, or an unbound PVC."),
        ("Pod in `CrashLoopBackOff`.",
         "`kubectl logs <pod> --previous` shows the crash from the *last* attempt — e.g. `Error: config not found`. The current container is often too young to have logged yet."),
        ("`Failed to pull image ...: ImagePullBackOff` on a private image.",
         "The node can't authenticate — attach an `imagePullSecret` to the ServiceAccount, and verify the `repository:tag` actually exists (`docker manifest inspect`)."),
        ("Service has Pods but traffic returns `503 Service Unavailable`.",
         "The Service `selector` doesn't match the Pod labels, or the readiness probe fails so Pods never join Endpoints. Check `kubectl get endpoints <svc>` — empty means broken wiring."),
        ("`kubectl apply` says `unchanged` / `configured` but nothing happens in prod.",
         "You applied to the wrong context/namespace. Confirm with `kubectl config current-context` and always pass `-n <namespace>`."),
    ],
    "docker": [
        ("Container exits immediately: `docker ps -a` shows `Exited (0)` or `Exited (1)`.",
         "The main process finished — a container lives only as long as PID 1. Run `docker logs <ctr>` and make sure `CMD` starts a foreground, long-running process (not one that daemonises)."),
        ("Image is huge and every build re-runs `npm install` / `pip install`.",
         "Cache busting. Copy `package.json`/`requirements.txt` and install BEFORE `COPY . .`, use a slim base, and add a `.dockerignore` so `.git`/`node_modules` don't bloat the context."),
        ("`docker: Error response from daemon: ... port is already allocated`.",
         "Another container/host process owns the host port. Find it with `docker ps` / `ss -tlnp` and pick a different left-hand `-p HOST:CONTAINER` value."),
        ("Data disappears when the container is removed.",
         "The writable layer is ephemeral. Persist state in a named volume (`-v data:/var/lib/...`), never the container filesystem."),
    ],
    "terraform": [
        ("`terraform apply` wants to `destroy` then `create` a resource you only renamed.",
         "Terraform keys on the resource address, not the cloud name. Use a `moved {}` block or `terraform state mv` to rename without recreating — re-plan should show `No changes`."),
        ("`Error acquiring the state lock` or two people corrupt state.",
         "Enable a remote backend with locking (S3 + DynamoDB, or TFC). Never share a local `terraform.tfstate`; `terraform force-unlock <id>` only after confirming no one is applying."),
        ("Plan shows changes every run even though nothing changed.",
         "Perpetual drift from a provider default or an attribute the API normalizes. Pin it explicitly, or add `lifecycle { ignore_changes = [tags[\"LastModified\"]] }`."),
        ("A secret ends up in `terraform.tfstate` in plaintext.",
         "State is sensitive by design — encrypt the backend, restrict access, and mark outputs `sensitive = true`. Never commit state to Git."),
    ],
    "ansible": [
        ("A task reports `changed` on every run even though it should be idempotent.",
         "You used `command`/`shell` where a real module exists. Switch to the module (`package`, `copy`, `lineinfile`) so state is compared, not blindly re-run; add `changed_when:` if you must use `command`."),
        ("`UNREACHABLE! => ... Failed to connect to the host via ssh` on hosts you can SSH to by hand.",
         "Ansible uses its own SSH user/key. Set `ansible_user`/`ansible_ssh_private_key_file` and test with `ansible <host> -m ping`."),
        ("A privileged task fails with `Permission denied`.",
         "You forgot `become: true` (or `-b`). Privilege escalation is off by default per play/task."),
        ("A variable resolves to the wrong value.",
         "Variable precedence bit you — `-e` extra-vars beat everything, role defaults lose to almost everything. Print it with `- debug: var=myvar` to confirm what actually won."),
    ],
    "aws": [
        ("`An error occurred (AccessDenied)` even though the IAM policy looks correct.",
         "An SCP, permissions boundary, or resource policy is denying — an explicit `Deny` always wins. Use the IAM Policy Simulator to see which statement blocks you."),
        ("EC2 instance is `running` but SSH hangs / times out.",
         "Security group, NACL, route table, or a missing public IP. Work outward: SG inbound 22 from your IP, subnet route to an IGW, then a public/elastic IP."),
        ("S3 objects return `403 Forbidden` despite a public bucket policy.",
         "Block Public Access is on at the account/bucket level and overrides the policy, or object ownership/ACLs disagree. Prefer bucket policies and disable BPA only where truly required."),
        ("Surprise NAT Gateway / data-transfer line item on the bill.",
         "Cross-AZ and NAT egress cost real money. Use VPC endpoints for S3/DynamoDB and keep chatty traffic within one AZ."),
    ],
    "database": [
        ("A query that was fast is suddenly slow.",
         "Stale statistics or a plan flip. Run `EXPLAIN (ANALYZE, BUFFERS)`; a `Seq Scan` where you expect an index means run `ANALYZE` or the index is missing/unusable."),
        ("`FATAL: remaining connection slots are reserved` / the app times out connecting.",
         "You've exhausted `max_connections`. Put a pooler (PgBouncer/ProxySQL) in front and cap the per-app pool — apps rarely need hundreds of direct connections."),
        ("Table keeps growing on disk after you `DELETE` rows.",
         "MVCC dead-tuple bloat — `DELETE` doesn't reclaim space. Tune autovacuum or `VACUUM (FULL)` in a window; watch dead tuples in `pg_stat_user_tables`."),
        ("Replica lag spikes under load and reads go stale.",
         "A long-running query or a write burst on the primary. Watch `pg_stat_replication`; offload heavy reads and avoid huge single transactions."),
        ("A restore fails during a real incident.",
         "The backup was never tested. Practice restores on a schedule — an untested backup is a hope, not a recovery plan."),
    ],
    "python": [
        ("`ModuleNotFoundError: No module named 'x'` even though you `pip install`ed it.",
         "Wrong interpreter/venv. Confirm with `which python` and `python -m pip list`; activate the venv or use `python -m pip install` so pip and python agree."),
        ("A function's default `[]`/`{}` keeps state between calls.",
         "`def f(x=[])` shares one list across all calls (evaluated once, at def time). Use `def f(x=None): x = x or []`."),
        ("Works locally but breaks in CI/prod.",
         "Unpinned dependencies or relying on the system Python. Pin versions in `requirements.txt`/a lockfile and run tests in the same container image."),
        ("An async service freezes under load.",
         "A blocking call (sync I/O, `time.sleep`, heavy CPU) inside the event loop. Move it to `asyncio.to_thread`/an executor, or use an async client."),
    ],
    "git": [
        ("You committed to the wrong branch.",
         "`git branch right-branch` then `git reset --hard origin/main` on the original — or `git reset --soft HEAD~1` to keep the change staged and re-commit elsewhere."),
        ("A merge conflict with `<<<<<<< HEAD` markers looks unresolvable.",
         "Conflicts are only overlapping edits. Open the file, keep the correct hunk between the markers, delete the markers, `git add`, then continue — or `git merge --abort` to retreat."),
        ("A secret got committed and pushed.",
         "Rotate it immediately — history is public the moment it's pushed. Rewriting history (`git filter-repo`) helps future clones, but the secret is already compromised."),
        ("`You are in 'detached HEAD' state` and you're worried you lost work.",
         "You didn't. `git reflog` shows every commit you were on; `git switch -c saved <hash>` turns any of them back into a branch."),
    ],
    "networking": [
        ("`ping` works but the app returns `Connection refused` / times out.",
         "ICMP is L3; the app is L4/L7. Test the actual port with `nc -vz host port` or `ss -tlnp`, and check firewall/security-group rules for that specific port."),
        ("DNS resolves to the wrong/old IP.",
         "Caching. Check the record's TTL and query the authoritative server directly with `dig @ns example.com`; flush local caches (`resolvectl flush-caches`)."),
        ("Intermittent packet loss or stalled large transfers.",
         "MTU/fragmentation or a duplex mismatch. Test path MTU with `ping -M do -s 1472 host` and check interface error counters (`ip -s link`)."),
        ("Traffic takes an unexpected path.",
         "A more-specific or wrong static route wins. Inspect with `ip route get <dst>` — longest-prefix match decides, not config order."),
    ],
    "security": [
        ("Over-broad IAM/RBAC grants nobody remembers approving.",
         "Start from deny, grant least privilege, and review access regularly. A wildcard (`Action: \"*\"`) in a policy is how one leaked key becomes a full breach."),
        ("Secrets in `.env` files or Git history.",
         "Move them to a vault with rotation and audit; scan the repo history (`gitleaks`) and rotate anything found. Env files leak via logs and images."),
        ("TLS 'works' but trusts anything (`verify=False`, `-k`).",
         "Certificate validation was disabled to 'make it work'. Fix the trust chain instead — a disabled check means you have no encryption guarantee at all."),
        ("Alerts fire constantly, so real ones get ignored.",
         "Tune detections to be actionable and map each to a runbook. Alert fatigue is itself a vulnerability."),
    ],
    "monitoring": [
        ("Dashboards are green but users report an outage.",
         "You're measuring the wrong SLI (host up, not request success). Alert on user-facing symptoms — error rate and latency — not just CPU/memory."),
        ("Alerts are noisy and page at 3am for a transient blip.",
         "Threshold alerting on a spiky metric. Use multi-window burn-rate alerts on an SLO so you page on sustained error-budget burn, not momentary spikes."),
        ("A dashboard query is slow or times out.",
         "Unbounded high-cardinality labels (per-request IDs). Aggregate with `sum by (...)`, add recording rules, and drop labels you never query."),
        ("You can see the latency spike but not *why*.",
         "Metrics show 'what', not 'why'. Add traces/exemplars so a latency spike links to the exact slow span/downstream call."),
    ],
    "vmware": [
        ("A VM is slow but in-guest CPU looks fine.",
         "Check %CPU Ready in esxtop/vCenter — the VM is waiting for physical cores. Reduce oversized vCPUs and host contention; a smaller VM is often faster."),
        ("Snapshots quietly fill the datastore.",
         "Snapshots are deltas that grow forever. Consolidate/delete them promptly; never treat a snapshot as a backup."),
        ("vMotion fails or a VM won't power on after a host issue.",
         "EVC/CPU compatibility or an orphaned lock. Check the host CPU baseline and clear stale `.lck` files; verify shared datastore access from the target host."),
        ("Storage latency spikes under load.",
         "Datastore contention or a failing path. Watch DAVG/KAVG in esxtop and check multipathing before blaming the application."),
    ],
    "windows": [
        ("A Group Policy change doesn't apply.",
         "Replication/precedence. Run `gpupdate /force`, check `gpresult /r` for the *winning* GPO, and confirm the OU link and security filtering."),
        ("A service fails to start after a reboot.",
         "A dependency or logon-account issue. Read the specific error in Event Viewer (System log) and check the service's recovery/dependency settings."),
        ("AD authentication intermittently fails.",
         "Time skew or DNS. Kerberos breaks past a 5-minute clock difference — verify `w32tm /query /status` and that clients use the DC for DNS."),
    ],
    "shell": [
        ("A script breaks on filenames with spaces / globs unexpectedly.",
         "Unquoted expansion (`SC2086`). Always quote: `\"$var\"`, `\"$@\"`; run `shellcheck` to catch it automatically."),
        ("A failing command in the middle doesn't stop the script.",
         "Bash keeps going by default. Start scripts with `set -euo pipefail` so errors, unset vars, and pipe failures abort immediately."),
        ("`command not found` in cron but it works in your interactive shell.",
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


def _clean_tagline(profile: dict, topic: str) -> str:
    """A short, sentence-safe noun phrase (lower-cased lead where appropriate)."""
    tag = (profile.get("tagline") or topic).strip().rstrip(".")
    if not tag:
        return topic.lower()
    first = tag.split(" ", 1)[0]
    # Leave the first word alone if it's an acronym/mixed-case brand (OCI, RHEL,
    # GitOps, PostgreSQL) — only down-case a plain capitalised English word.
    if first[:1].isupper() and first[1:].islower():
        return tag[:1].lower() + tag[1:]
    return tag


# ── Section writers ─────────────────────────────────────────────────────────


def _write_overview(topic: str, module: str, level: str, profile: dict, course_slug: str = "") -> str:
    tagline = _clean_tagline(profile, topic)
    arch = profile.get("architecture", "")
    analogy = _analogy_for(topic, course_slug)
    why = _why_for(topic, course_slug)
    diagram = _arch_diagram(module, profile, topic=topic, course_slug=course_slug)

    body = (
        f"## Overview\n\n"
        f"This module covers **{module}** — one focused slice of {topic} ({tagline}). "
        f"By the end you'll be able to explain it in plain English, run the core commands, "
        f"and recognise the failures it causes when it's misconfigured.\n\n"
    )
    if analogy:
        body += f"**In plain terms.** {analogy}\n\n"
    body += f"**Why it matters.** {why}\n\n"
    if arch:
        body += f"**How it fits together.** {arch}\n\n"
    body += (
        "The diagram below is the mental model for this module — the one picture to keep in your head. "
        "Everything in the walkthrough moves through these components.\n\n"
        f"{diagram}"
    )
    return body


def _write_concepts(topic: str, module: str, level: str, profile: dict, course_slug: str = "") -> str:
    items = _match_concepts(profile, module, topic, course_slug)
    body = (
        f"## Key concepts\n\n"
        f"The handful of ideas that actually matter for **{module}**. If you can explain each in one "
        f"sentence, the walkthrough will make sense.\n\n"
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
    # ONE comparison table. Prefer a topic-relevant "at a glance" table built from
    # the real concepts; fall back to the control/data split only when we have none.
    body += "\n\n" + _concepts_table(items, module, topic, course_slug)
    return body


# Primary "how do I see this?" command per topic bucket — used as the table's
# default check column when a concept description carries no `code` token.
_INSPECT_CMD: dict[str, str] = {
    "linux": "`ls -l` / `id` / `systemctl status`",
    "kubernetes": "`kubectl get` / `describe`",
    "docker": "`docker inspect`",
    "terraform": "`terraform state show`",
    "ansible": "`ansible -m setup` / `--check`",
    "aws": "`aws ... describe-*`",
    "database": "`\\d` / `SELECT ... FROM pg_*`",
    "git": "`git show` / `git log`",
    "networking": "`ip` / `ss` / `dig`",
    "monitoring": "a PromQL query",
    "vmware": "`govc ... .info`",
    "windows": "`Get-*` / Event Viewer",
    "python": "`python -c` / `pip show`",
    "shell": "`shellcheck` / `bash -x`",
}


def _concepts_table(items: list[tuple[str, str]], module: str, topic: str = "", course_slug: str = "") -> str:
    """A skimmable 'at a glance' table of the concepts, with a how-to-verify column."""
    if items:
        default_check = _INSPECT_CMD.get(_topic_key(topic, course_slug), "inspect its status / config")
        rows = ["| Concept | In one line | How to check / where it lives |", "|---|---|---|"]
        for name, desc in items[:4]:
            one_line = desc.split(".")[0].strip()
            # Pull a `code` token from the description as the "how to check", if present.
            code = re.search(r"`([^`]+)`", desc)
            check = f"`{code.group(1)}`" if code else default_check
            rows.append(f"| {name} | {one_line} | {check} |")
        return "\n".join(rows)
    return (
        "| Term | What it means | How to verify |\n"
        "|---|---|---|\n"
        f"| {module} | The subject of this module | Its status/health check returns healthy |\n"
        "| Control plane | Manages configuration & policy | API/UI responds; no config drift |\n"
        "| Data plane | Serves user/workload traffic | End-to-end synthetic check passes |\n"
    )


def _shell_block(steps: list[tuple[str, str, str]]) -> str:
    """Render a single ```bash block: each command `$`-prefixed with its output below.

    Guarantees the completeness gate's SHELL_WITH_OUTPUT pattern (a `$ ` line
    followed by a non-`$`, non-fence line) whenever any step has output.
    """
    lines = ["```bash"]
    for _narration, cmd, out in steps:
        cmd_lines = cmd.splitlines() or [cmd]
        lines.append(f"$ {cmd_lines[0]}")
        lines.extend(cmd_lines[1:])  # continuation lines of a multi-line command
        if out:
            lines.extend(out.splitlines())
    lines.append("```")
    return "\n".join(lines)


def _write_walkthrough(topic: str, module: str, level: str, profile: dict, playground: str, course_slug: str = "") -> str:
    from apps.tutorials.course_diagrams import command_sequence_diagram

    steps = _worked_for(topic, course_slug) or _generic_worked(topic, module, profile)

    intro = (
        f"## Hands-on walkthrough\n\n"
        f"Run this in the **{topic}** playground (`{playground}`) or the linked lab. We'll follow the "
        f"loop every good operator uses: **inspect → change one thing → verify**. Each command is on a "
        f"`$` line with the output you should expect right below it, so you can compare your terminal to "
        f"the baseline after every step.\n\n"
    )

    if steps:
        # A real, narrated worked example: numbered narration + one shell block +
        # the same steps as a sequence diagram.
        narration_lines = []
        for i, (narration, cmd, _out) in enumerate(steps, start=1):
            first = cmd.splitlines()[0]
            narration_lines.append(f"{i}. **{narration}**  \n   `{first}`")
        walkthrough = "\n".join(narration_lines)
        shell = _shell_block(steps)
        cmd_list = [c for _n, c, _o in steps]
        seq = command_sequence_diagram(cmd_list, topic, module)
    else:
        # Fallback: use the profile's commands (still real syntax) + a sample block.
        from apps.tutorials.course_diagrams import shell_block_with_output

        cmds = profile.get("commands") or {}
        fb = _fallback_for(topic)
        if not cmds and fb:
            cmds = {"steps": fb[1].get("labs", "")}
        shell = shell_block_with_output(cmds, topic, module)
        if not shell:
            first = next(iter(cmds.values()), f"# Practice {module}\nhelp | head -5")
            shell = f"```bash\n{first}\n```"
        walkthrough = (
            "1. **Inspect first** — run the primary command and save its output as your baseline.\n"
            "2. **Change one thing** — make a single reversible change that targets the symptom.\n"
            "3. **Verify** — re-run the same command and diff against the baseline."
        )
        seq = command_sequence_diagram(cmds, topic, module)

    seq_block = (
        f"\n\nThe same steps as an interaction — who talks to what, in order:\n\n{seq}"
        if seq
        else ""
    )

    return (
        f"{intro}"
        f"{walkthrough}\n\n"
        f"{shell}\n\n"
        f"> [!TIP] The discipline that separates guessing from engineering: change **one** thing, then "
        f"re-run the exact same command and diff the output against the baseline above. That diff is your "
        f"evidence the change did what you intended — and only that.{seq_block}"
    )


def _write_pitfalls(topic: str, module: str, level: str, profile: dict, course_slug: str = "") -> str:
    pitfalls = _pitfalls_for(topic, course_slug)
    body = (
        f"## Common pitfalls & fixes\n\n"
        f"The failures that actually bite people with {topic}. For each: the symptom you'll see "
        f"(often the literal error), then the fix.\n\n"
    )
    for i, (symptom, fix) in enumerate(pitfalls, start=1):
        body += f"**{i}. {symptom}**\n\n{fix}\n\n"
    body += (
        "> [!GOTCHA] Before any invasive action, capture logs and current state first — "
        "a blind restart often clears the very evidence you need for root cause, and the problem returns."
    )
    return body


def _write_assess(topic: str, module: str, level: str, profile: dict, playground: str, scenario: str, course_slug: str = "") -> str:
    lab_line = (
        f"[Run in lab →](/scenarios/{scenario})"
        if scenario
        else f"Open the **{topic}** playground (`{playground}`) and reproduce a failure, then fix it."
    )
    body = (
        f"## Practice & assess\n\n"
        f"**Do the lab.** {lab_line}\n\n"
        f"Reproduce the failure, apply one fix at a time, and verify with the same commands from the "
        f"walkthrough. Use **Check Solution** — the lab grades real system state, not marker files.\n\n"
    )
    # Quick-reference cheat sheet: the commands to reach for under pressure.
    cheats = _cheatsheet_for(topic, course_slug)
    if cheats:
        body += (
            "**Quick reference — commands you'll reach for.**\n\n"
            "| Task | Command |\n|---|---|\n"
            + "\n".join(f"| {task} | {cmd} |" for task, cmd in cheats)
            + "\n\n"
        )
    body += (
        f"**Then take the quiz.** Answer the five-question module quiz below. You pass this lesson when "
        f"your quiz score is **80% or higher** and the linked hands-on lab is complete. {_level_note(level)}"
    )
    return body


def _write_takeaways(topic: str, module: str, level: str, profile: dict, course_slug: str = "") -> str:
    concepts = _match_concepts(profile, module, topic, course_slug)
    slo = profile.get("slo", "availability, latency p99, error rate, saturation")
    tagline = _clean_tagline(profile, topic)
    bullets = [
        f"**{module}** is about {tagline} — keep the Overview diagram as your mental model.",
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


def _build_code(section_key: str, topic: str, module: str, profile: dict, course_slug: str = "") -> tuple[str, str, str]:
    """Section-level code block (rendered in the dedicated code pane).

    Only the walkthrough carries a code block now — the shell command sequence
    for the module. Keeping this on the model field (not just in-body) preserves
    the ShellBlock output-pane rendering the frontend expects. Prefers the concrete
    worked-example commands so the code pane matches the narrated walkthrough.
    """
    if section_key != "walkthrough":
        return "", "text", ""
    steps = _worked_for(topic, course_slug) or _generic_worked(topic, module, profile)
    if steps:
        body = "\n".join(c for _n, c, _o in steps)
        return f"# {module}\n{body}", "bash", f"{topic} hands-on — run in playground"
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
            body = _write_concepts(topic, module_title, level, profile, course_slug)
        elif key == "walkthrough":
            body = _write_walkthrough(topic, module_title, level, profile, playground, course_slug)
        elif key == "pitfalls":
            body = _write_pitfalls(topic, module_title, level, profile, course_slug)
        elif key == "assess":
            body = _write_assess(topic, module_title, level, profile, playground, scenario, course_slug)
        else:  # takeaways
            body = _write_takeaways(topic, module_title, level, profile, course_slug)
        code, lang, caption = _build_code(key, topic, module_title, profile, course_slug)
        sections.append((heading, body, code, lang, caption))
    return sections
