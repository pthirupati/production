"""Management command: seed_learning_journeys

Authors a small, curated set of named, role-based Learning Journeys that BUNDLE
already-existing FixitLab content (a Zero-to-Hero tutorial course + a
difficulty-ordered set of scenarios + a capstone project + the matching
certification track) into a single milestone path.

Every reference below points at REAL, already-seeded content — the slugs were
confirmed against a fully-seeded catalog (seed_scenarios / seed_projects /
seed_certifications / seed_tutorials). Journeys own no content: they reference
it loosely by slug, so a missing/renamed target degrades gracefully rather than
404-ing the whole journey.

Idempotent: update_or_create on the journey slug, and steps are fully rebuilt
each run so re-seeding always converges to the authored definition.

Usage:
    python manage.py seed_learning_journeys
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.question_bank.models import (
    LearningJourney,
    JourneyStep,
    Technology,
)


# ─── Authored journeys ───────────────────────────────────────────────────────
#
# Each step's ``ref``/``refs`` were verified to exist in the seeded catalog:
#   * tutorial_course -> course_slug from apps.tutorials course catalog
#   * scenarios       -> Scenario.slug (difficulty-ordered easy->medium->hard)
#   * project         -> Project.slug (a capstone where one exists)
#   * certification   -> CertificationTrack.slug
#   * milestone       -> no ref (an achievement marker)
#
JOURNEYS = [
    {
        "slug": "junior-linux-admin-rhcsa",
        "title": "Junior Linux Admin → RHCSA",
        "role_label": "Junior Linux Admin",
        "level": "beginner",
        "primary_tech": "linux",
        "description": (
            "Go from zero Linux to a job-ready junior administrator and sit the "
            "RHCSA mock exam. Learn the fundamentals, ramp through hands-on labs "
            "easy → hard, build a real server, then prove it on the certification "
            "track."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn the fundamentals: Linux SysAdmin Zero-to-Hero",
             "ref": "linux-sysadmin-zero-hero", "est": 600,
             "description": "Work through the full Linux SysAdmin course from first login to services and storage."},
            {"kind": "scenarios", "title": "Warm-up labs: users, permissions & services",
             "refs": ["academy-linux-001-learn-users-groups",
                      "academy-linux-002-build-permissions-acl",
                      "academy-linux-003-operate-systemd-services"], "est": 120,
             "description": "Difficulty-ordered starter labs — users/groups, permissions/ACLs, and systemd services."},
            {"kind": "scenarios", "title": "Level up: networking & firewalld hardening",
             "refs": ["academy-linux-006-security-networking-firewalld"], "est": 60,
             "description": "A harder lab: secure the box with firewalld and fix networking."},
            {"kind": "project", "title": "Build a real server from zero",
             "ref": "linux-fundamentals-first-server", "est": 180,
             "description": "Guided project: provision and configure your first production-shaped Linux server."},
            {"kind": "project", "title": "Storage engineering: LVM, filesystems & quotas",
             "ref": "linux-lvm-storage-build", "est": 240,
             "description": "Capstone-style storage build to consolidate the RHCSA storage domain."},
            {"kind": "certification", "title": "Earn it: RHCSA certification track",
             "ref": "rhcsa", "est": 180,
             "description": "Run the objective-mapped RHCSA labs and take the timed mock exam."},
            {"kind": "milestone", "title": "Milestone: RHCSA-ready Junior Linux Admin",
             "est": None,
             "description": "You can administer a Linux server end-to-end and have passed the RHCSA mock exam."},
        ],
    },
    {
        "slug": "cloud-engineer-terraform-aws",
        "title": "Cloud Engineer → Terraform Associate",
        "role_label": "Cloud Engineer",
        "level": "intermediate",
        "primary_tech": "terraform",
        "description": (
            "Become a cloud engineer who provisions infrastructure as code. Learn "
            "Terraform and AWS, ramp through IaC labs, ship a full 3-tier VPC "
            "capstone, and certify with the Terraform Associate track."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn IaC: Terraform Zero-to-Hero",
             "ref": "terraform-iac-zero-hero", "est": 540,
             "description": "The full Terraform course: providers, state, modules, and remote backends."},
            {"kind": "tutorial_course", "title": "Learn the platform: AWS Cloud Zero-to-Hero",
             "ref": "aws-cloud-zero-hero", "est": 540,
             "description": "Core AWS: EC2, S3, VPC networking, and IAM — the substrate your Terraform manages."},
            {"kind": "scenarios", "title": "Terraform labs: providers → variables → remote backend",
             "refs": ["academy-terraform-001-learn-providers",
                      "academy-terraform-003-operate-variables",
                      "academy-terraform-006-security-remote-backend"], "est": 150,
             "description": "Difficulty-ordered Terraform labs from first apply to a secured remote backend."},
            {"kind": "project", "title": "Provision a full 3-tier VPC with Terraform",
             "ref": "terraform-3tier-vpc-iac", "est": 240,
             "description": "Build a real multi-tier network entirely as code."},
            {"kind": "project", "title": "Capstone: IaC to Live — Terraform → Ansible → App → Monitoring",
             "ref": "capstone-terraform-ansible-app-monitoring", "est": 360,
             "description": "End-to-end capstone: provision with Terraform, configure with Ansible, deploy, and observe."},
            {"kind": "certification", "title": "Earn it: Terraform Associate track",
             "ref": "terraform-associate", "est": 180,
             "description": "Objective-mapped Terraform Associate labs plus the timed mock exam."},
            {"kind": "milestone", "title": "Milestone: Certified Cloud Engineer",
             "est": None,
             "description": "You can design and provision multi-tier cloud infrastructure as code and passed the Terraform Associate mock."},
        ],
    },
    {
        "slug": "kubernetes-sre-cka",
        "title": "Kubernetes SRE → CKA",
        "role_label": "Kubernetes SRE",
        "level": "advanced",
        "primary_tech": "kubernetes",
        "description": (
            "Operate Kubernetes in production and pass the CKA. Learn the platform, "
            "ramp through pods → services → secrets, run an autoscaling & "
            "observability capstone, and certify."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn the platform: Kubernetes Zero-to-Hero",
             "ref": "kubernetes-platform-zero-hero", "est": 600,
             "description": "The full Kubernetes course: pods, deployments, services, storage, and RBAC."},
            {"kind": "scenarios", "title": "Core labs: pods → services → secrets",
             "refs": ["academy-kubernetes-001-learn-pods",
                      "academy-kubernetes-003-operate-services",
                      "academy-kubernetes-006-security-secrets"], "est": 150,
             "description": "Difficulty-ordered Kubernetes labs from first pod to securing secrets."},
            {"kind": "project", "title": "Deploy a full app stack on Kubernetes",
             "ref": "k8s-full-stack-deploy", "est": 300,
             "description": "Ship a real multi-service application onto a cluster."},
            {"kind": "project", "title": "Capstone: Autoscaling, Observability & Cluster Troubleshooting",
             "ref": "k8s-autoscaling-observability-capstone", "est": 360,
             "description": "SRE capstone — autoscale, observe, and debug a cluster under load."},
            {"kind": "certification", "title": "Earn it: CKA certification track",
             "ref": "cka", "est": 240,
             "description": "Objective-mapped CKA labs plus the timed mock exam."},
            {"kind": "milestone", "title": "Milestone: CKA-ready Kubernetes SRE",
             "est": None,
             "description": "You can operate, scale, and troubleshoot production Kubernetes and passed the CKA mock exam."},
        ],
    },
    {
        "slug": "devsecops-engineer-supply-chain",
        "title": "DevSecOps Engineer → Secure Supply Chain",
        "role_label": "DevSecOps Engineer",
        "level": "advanced",
        "primary_tech": "devsecops-supplychain",
        "description": (
            "Own software supply-chain security. Learn DevSecOps, ramp through CVE "
            "scanning → image signing → leaked-secret forensics, and prove it with "
            "an end-to-end secure-SDLC capstone."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn the discipline: DevSecOps Zero-to-Hero",
             "ref": "devsecops-zero-hero", "est": 540,
             "description": "Shift security left: scanning, SBOMs, signing, provenance, and runtime detection."},
            {"kind": "scenarios", "title": "Supply-chain labs: CVE → unsigned image → leaked secret",
             "refs": ["devsecops-trivy-critical-cve",
                      "devsecops-cosign-unsigned-image",
                      "devsecops-secret-leaked-layer"], "est": 150,
             "description": "Difficulty-ordered supply-chain labs from a critical CVE to a secret leaked in an image layer."},
            {"kind": "project", "title": "Fix a critical CVE before it ships",
             "ref": "devsecops-fix-critical-cve", "est": 180,
             "description": "Catch and remediate a critical vulnerability in the pipeline."},
            {"kind": "project", "title": "Sign and verify images with Cosign",
             "ref": "devsecops-cosign-sign-verify", "est": 180,
             "description": "Add cryptographic signing and verification to your image supply chain."},
            {"kind": "project", "title": "Capstone: Secure Supply Chain — Scan, Sign, and Enforce",
             "ref": "capstone-secure-sdlc-supply-chain", "est": 360,
             "description": "End-to-end capstone: scan, sign, generate provenance, and enforce policy in a real pipeline."},
            {"kind": "milestone", "title": "Milestone: Supply-Chain-Ready DevSecOps Engineer",
             "est": None,
             "description": "You can secure a software supply chain end-to-end: scan, sign, attest, and enforce."},
        ],
    },
    {
        "slug": "sre-incident-responder",
        "title": "SRE / Incident Responder",
        "role_label": "Site Reliability Engineer",
        "level": "advanced",
        "primary_tech": "prometheus",
        "description": (
            "Keep production up and respond to incidents like an SRE. Learn "
            "Prometheus & Grafana observability, ramp through scrape → alerts → "
            "remote-write, survive a Black-Friday incident capstone, and run a live "
            "incident with the Incident Director."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn observability: Prometheus & Grafana Zero-to-Hero",
             "ref": "prometheus-grafana-zero-hero", "est": 540,
             "description": "Metrics, PromQL, dashboards, and alerting — the SRE observability stack."},
            {"kind": "scenarios", "title": "Observability labs: scrape → alerts → remote-write",
             "refs": ["academy-prometheus-001-learn-scrape-config",
                      "academy-prometheus-003-operate-alerts",
                      "academy-prometheus-006-security-remote-write"], "est": 150,
             "description": "Difficulty-ordered Prometheus labs from first scrape to secured remote-write."},
            {"kind": "project", "title": "Build your first Grafana dashboard",
             "ref": "grafana-first-dashboard", "est": 120,
             "description": "Connect a datasource and build a real dashboard from scratch."},
            {"kind": "project", "title": "Capstone: Black Friday Incident — Survive the Traffic",
             "ref": "capstone-black-friday-sre-incident", "est": 360,
             "description": "SRE capstone: keep the store up through a Black-Friday traffic surge."},
            {"kind": "project", "title": "SRE Capstone: Reliability, Load Testing & Incident Response",
             "ref": "devops-sre-capstone", "est": 360,
             "description": "Define SLOs, load-test to failure, and run the incident to resolution."},
            {"kind": "milestone", "title": "Milestone: Run a live incident with the Incident Director",
             "est": None,
             "description": "Lead a live, timed incident in the multiplayer War-Room / Incident Director and produce a postmortem."},
        ],
    },
    {
        "slug": "aws-cloud-beginner",
        "title": "AWS Cloud Beginner",
        "role_label": "Junior Cloud Engineer",
        "level": "beginner",
        "primary_tech": "aws",
        "description": (
            "Start from zero AWS. Learn the core platform, then ramp through "
            "EC2 → S3 → IAM labs and a second wave of VPC, security groups, and "
            "CloudWatch before you call yourself cloud-ready."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn the platform: AWS Cloud Zero-to-Hero",
             "ref": "aws-cloud-zero-hero", "est": 540,
             "description": "Core AWS: EC2, S3, VPC networking, and IAM — the foundation every cloud role builds on."},
            {"kind": "scenarios", "title": "Warm-up labs: EC2 → S3 → IAM",
             "refs": ["academy-aws-001-learn-ec2",
                      "academy-aws-002-build-s3",
                      "academy-aws-003-operate-iam"], "est": 120,
             "description": "Difficulty-ordered starter labs — launch compute, store objects, and operate IAM."},
            {"kind": "scenarios", "title": "Level up: VPC, security groups & CloudWatch",
             "refs": ["academy-aws-004-troubleshoot-vpc",
                      "academy-aws-005-production-security-groups",
                      "academy-aws-008-observability-cloudwatch"], "est": 120,
             "description": "Harden networking and start watching what your resources actually do."},
            {"kind": "scenarios", "title": "Keep going: Lambda automation & backups",
             "refs": ["academy-aws-007-automation-lambda",
                      "academy-aws-009-backup-autoscaling"], "est": 90,
             "description": "Touch serverless automation and autoscaling backup patterns."},
            {"kind": "milestone", "title": "Milestone: AWS Cloud Beginner",
             "est": None,
             "description": "You can navigate core AWS services — compute, storage, identity, networking, and basic observability."},
        ],
    },
    {
        "slug": "python-devops-beginner",
        "title": "Python Beginner",
        "role_label": "Junior Python Developer",
        "level": "beginner",
        "primary_tech": "python",
        "description": (
            "Go from zero Python to a job-ready junior. Learn the DevOps-flavored "
            "Python course, ramp through venv → files → HTTP API labs, then "
            "level up with testing, logging, and exceptions."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn the language: Python DevOps Zero-to-Hero",
             "ref": "python-devops-zero-hero", "est": 540,
             "description": "Python for operators and builders: environments, scripts, APIs, and packaging."},
            {"kind": "scenarios", "title": "Warm-up labs: venv → files → HTTP API",
             "refs": ["academy-python-001-learn-venv",
                      "academy-python-002-build-files",
                      "academy-python-003-operate-http-api"], "est": 120,
             "description": "Difficulty-ordered starter labs — virtualenvs, file I/O, and a small HTTP API."},
            {"kind": "scenarios", "title": "Level up: testing, logging & exceptions",
             "refs": ["academy-python-004-troubleshoot-testing",
                      "academy-python-005-production-logging",
                      "academy-python-006-security-exceptions"], "est": 120,
             "description": "Prove behavior with tests, log like production, and handle failures safely."},
            {"kind": "project", "title": "Build a real CLI from scratch",
             "ref": "python-cli-fundamentals", "est": 180,
             "description": "Guided project: ship a small Python CLI with arguments, errors, and usable output."},
            {"kind": "milestone", "title": "Milestone: Python Beginner",
             "est": None,
             "description": "You can set up environments, write scripts and small APIs, and ship a basic Python CLI."},
        ],
    },
    {
        "slug": "docker-containers-beginner",
        "title": "Docker Beginner",
        "role_label": "Junior Container Engineer",
        "level": "beginner",
        "primary_tech": "docker",
        "description": (
            "Learn containers from first principles. Work through Docker "
            "Zero-to-Hero, ramp images → Dockerfile → Compose, then harden with "
            "volumes, networks, and healthchecks."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn containers: Docker Zero-to-Hero",
             "ref": "docker-containers-zero-hero", "est": 540,
             "description": "Images, containers, Dockerfiles, volumes, networking, and Compose."},
            {"kind": "scenarios", "title": "Warm-up labs: images → Dockerfile → Compose",
             "refs": ["academy-docker-001-learn-images-layers",
                      "academy-docker-002-build-dockerfile",
                      "academy-docker-003-operate-compose"], "est": 120,
             "description": "Difficulty-ordered starter labs — layers, building images, and multi-service Compose."},
            {"kind": "scenarios", "title": "Level up: volumes, networks & healthchecks",
             "refs": ["academy-docker-004-troubleshoot-volumes",
                      "academy-docker-005-production-networks",
                      "academy-docker-006-security-healthchecks"], "est": 120,
             "description": "Persist data, wire networks, and keep containers honest with healthchecks."},
            {"kind": "project", "title": "Ship your first containerized app",
             "ref": "docker-fundamentals", "est": 180,
             "description": "Guided project: containerize an app end-to-end with a sensible image and run story."},
            {"kind": "milestone", "title": "Milestone: Docker Beginner",
             "est": None,
             "description": "You can build images, run Compose stacks, and troubleshoot common container failures."},
        ],
    },
    {
        "slug": "security-hardening-beginner",
        "title": "Security Beginner",
        "role_label": "Junior Security Engineer",
        "level": "beginner",
        "primary_tech": "security",
        "description": (
            "Build security fundamentals hands-on. Learn cybersecurity basics, "
            "ramp SSH hardening → firewall → TLS, then level up with secrets, "
            "audit, and IAM before a first hardened-host project."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn the discipline: Cybersecurity Zero-to-Hero",
             "ref": "cybersecurity-zero-hero", "est": 540,
             "description": "Core security mindset: hardening, network controls, TLS, secrets, and least privilege."},
            {"kind": "scenarios", "title": "Warm-up labs: SSH → firewall → TLS",
             "refs": ["academy-security-001-learn-ssh-hardening",
                      "academy-security-002-build-firewall",
                      "academy-security-003-operate-tls"], "est": 120,
             "description": "Difficulty-ordered starter labs — lock down SSH, build a firewall, and operate TLS."},
            {"kind": "scenarios", "title": "Level up: secrets, audit & IAM",
             "refs": ["academy-security-004-troubleshoot-secrets",
                      "academy-security-005-production-audit",
                      "academy-security-006-security-iam"], "est": 120,
             "description": "Find leaked secrets, read audit trails, and tighten identity."},
            {"kind": "project", "title": "Harden a host from zero",
             "ref": "security-fundamentals", "est": 180,
             "description": "Guided project: apply baseline hardening to a real host-shaped environment."},
            {"kind": "milestone", "title": "Milestone: Security Beginner",
             "est": None,
             "description": "You can harden SSH, firewalls, and TLS and reason about secrets and least privilege."},
        ],
    },
    {
        "slug": "ai-data-beginner",
        "title": "AI & Data Beginner",
        "role_label": "Junior AI / Data Practitioner",
        "level": "beginner",
        "primary_tech": "ai-ml",
        "description": (
            "Start the AI and data path. Learn AI infrastructure fundamentals, "
            "work a dataset lab plus a data-cleaning lab, then level up with "
            "features, training, joins, and groupbys."
        ),
        "steps": [
            {"kind": "tutorial_course", "title": "Learn the stack: AI Infrastructure Zero-to-Hero",
             "ref": "ai-infrastructure-zero-hero", "est": 540,
             "description": "How models, datasets, and serving pieces fit together in a practical AI stack."},
            {"kind": "tutorial_course", "title": "Learn the craft: Data Science Zero-to-Hero",
             "ref": "data-science-zero-hero", "est": 540,
             "description": "Cleaning, joins, aggregations, and the everyday data workflow beside the model path."},
            {"kind": "scenarios", "title": "Warm-up labs: dataset + data cleaning",
             "refs": ["academy-ai-ml-001-learn-dataset",
                      "academy-data-science-001-learn-cleaning"], "est": 90,
             "description": "First hands-on: load and understand a dataset, then clean real messy data."},
            {"kind": "scenarios", "title": "Level up: features, training, joins & groupby",
             "refs": ["academy-ai-ml-002-build-features",
                      "academy-ai-ml-003-operate-training",
                      "academy-data-science-002-build-joins",
                      "academy-data-science-003-operate-groupby"], "est": 150,
             "description": "Build features, run a training loop, and practice joins/groupbys on tabular data."},
            {"kind": "milestone", "title": "Milestone: AI & Data Beginner",
             "est": None,
             "description": "You can load datasets, clean tabular data, build basic features, and follow a simple training path."},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed named role-based Learning Journeys that bundle existing content."

    @transaction.atomic
    def handle(self, *args, **options):
        created_j = updated_j = 0
        total_steps = 0

        for spec in JOURNEYS:
            tech = None
            tech_slug = spec.get("primary_tech")
            if tech_slug:
                tech = Technology.objects.filter(slug=tech_slug).first()
                if tech is None:
                    self.stderr.write(self.style.WARNING(
                        f"  primary_tech {tech_slug!r} not found for {spec['slug']} — leaving null"
                    ))

            journey, created = LearningJourney.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "title": spec["title"],
                    "role_label": spec.get("role_label", ""),
                    "description": spec.get("description", ""),
                    "level": spec.get("level", "beginner"),
                    "primary_technology": tech,
                    "order": JOURNEYS.index(spec),
                    "is_active": True,
                },
            )
            if created:
                created_j += 1
            else:
                updated_j += 1

            # Rebuild steps deterministically so re-seeding converges.
            journey.steps.all().delete()
            for i, step in enumerate(spec["steps"]):
                JourneyStep.objects.create(
                    journey=journey,
                    order=i,
                    kind=step["kind"],
                    title=step["title"],
                    description=step.get("description", ""),
                    ref_slug=step.get("ref", ""),
                    ref_slugs=step.get("refs", []),
                    est_minutes=step.get("est"),
                )
                total_steps += 1

            self.stdout.write(
                f"  {'Created' if created else 'Updated'}: {journey.title} "
                f"({journey.steps.count()} steps)"
            )

        self.stdout.write(self.style.SUCCESS(
            f"Learning journeys seeded: {created_j} created, {updated_j} updated, "
            f"{total_steps} steps total."
        ))
