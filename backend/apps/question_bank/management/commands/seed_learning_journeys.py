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
