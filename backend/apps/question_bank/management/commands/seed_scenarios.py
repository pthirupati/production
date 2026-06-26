"""
Management command: seed_scenarios
Loads scenario definitions from YAML files in the scenarios/ directory.
Usage: python manage.py seed_scenarios
"""

import os
import yaml
from django.core.management.base import BaseCommand
from apps.question_bank.models import Technology, Scenario
from apps.hints.models import Hint

TECH_META = {
    "linux": {"slug": "linux", "name": "Linux Administration", "icon": "terminal", "color": "cyan", "order": 5},
    "networking": {"slug": "networking", "name": "Networking", "icon": "globe", "color": "blue", "order": 7},
    "vmware": {"slug": "vmware", "name": "VMware vSphere", "icon": "server", "color": "blue", "order": 8},
    "database": {"slug": "database", "name": "Database Administration", "icon": "database", "color": "blue", "order": 10},
    "docker": {"slug": "docker", "name": "Docker & Containers", "icon": "container", "color": "cyan", "order": 11},
    "ansible": {"slug": "ansible", "name": "Ansible Automation", "icon": "network", "color": "purple", "order": 12},
    "kubernetes": {"slug": "kubernetes", "name": "Kubernetes", "icon": "layers", "color": "indigo", "order": 13},
    "baremetal": {"slug": "baremetal", "name": "Bare Metal & IPMI", "icon": "server", "color": "orange", "order": 14},
    "gpu": {"slug": "gpu", "name": "GPU & NVIDIA", "icon": "cpu", "color": "green", "order": 15},
    "python": {"slug": "python", "name": "Python Development", "icon": "code", "color": "yellow", "order": 16},
    "java": {"slug": "java", "name": "Java Development", "icon": "code", "color": "orange", "order": 17},
    "html": {"slug": "html", "name": "HTML & Web Servers", "icon": "globe", "color": "pink", "order": 18},
    "shell-script": {"slug": "shell-script", "name": "Shell Scripting", "icon": "terminal", "color": "teal", "order": 19},
    "devops": {"slug": "devops", "name": "DevOps", "icon": "layers", "color": "purple", "order": 20},
    "security": {"slug": "security", "name": "Security", "icon": "shield", "color": "red", "order": 21},
    "grafana": {"slug": "grafana", "name": "Grafana Observability", "icon": "activity", "color": "orange", "order": 22},
    "prometheus": {"slug": "prometheus", "name": "Prometheus Monitoring", "icon": "activity", "color": "red", "order": 23},
    "prompt-engineering": {"slug": "prompt-engineering", "name": "Prompt Engineering & AI Mastery", "icon": "sparkles", "color": "purple", "order": 1, "price": 0},
    "javascript": {"slug": "javascript", "name": "JavaScript", "icon": "code", "color": "yellow", "order": 24},
    "nodejs": {"slug": "nodejs", "name": "Node.js", "icon": "code", "color": "green", "order": 25},
    "react": {"slug": "react", "name": "React", "icon": "layers", "color": "cyan", "order": 26},
    "postgresql": {"slug": "postgresql", "name": "PostgreSQL", "icon": "database", "color": "blue", "order": 27},
    "mysql": {"slug": "mysql", "name": "MySQL", "icon": "database", "color": "blue", "order": 28},
    "sqlite": {"slug": "sqlite", "name": "SQLite", "icon": "database", "color": "teal", "order": 29},
    "rhel-linux": {"slug": "rhel-linux", "name": "RHEL Linux", "icon": "terminal", "color": "red", "order": 6},
    "nmap": {"slug": "nmap", "name": "Nmap Network Scanning", "icon": "globe", "color": "green", "order": 30},
    "wireshark": {"slug": "wireshark", "name": "Wireshark Packet Analysis", "icon": "activity", "color": "blue", "order": 31},
    "peoplesoft": {"slug": "peoplesoft", "name": "PeopleSoft Administration", "icon": "server", "color": "orange", "order": 32},
    "simulation": {"slug": "simulation", "name": "IT Simulation Labs", "icon": "layers", "color": "purple", "order": 33},
    "ai-ml": {"slug": "ai-ml", "name": "AI & Machine Learning", "icon": "sparkles", "color": "purple", "order": 2},
    "data-science": {"slug": "data-science", "name": "Data Science", "icon": "activity", "color": "pink", "order": 3},
    "windows": {"slug": "windows", "name": "Windows Server", "icon": "server", "color": "blue", "order": 9},
}


class Command(BaseCommand):
    help = "Seed the database with scenario definitions from YAML files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="/scenarios",
            help="Root directory containing scenario YAML files",
        )
        parser.add_argument(
            "--technologies",
            default="",
            help="Comma-separated technology folder slugs to seed (default: all)",
        )
        parser.add_argument(
            "--merge-only",
            action="store_true",
            help="Only create new scenarios; do not overwrite existing scenario fields",
        )

    def _load_technology(self, tech_dir: str, tech_path: str) -> Technology:
        meta_path = os.path.join(tech_path, "technology.yaml")
        meta = dict(TECH_META.get(tech_dir, {}))
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                file_meta = yaml.safe_load(f) or {}
                meta.update(file_meta)

        name = meta.get("name") or tech_dir.replace("-", " ").title()
        defaults = {
            "icon": meta.get("icon", "terminal"),
            "color": meta.get("color", "cyan"),
            "description": meta.get("description", f"{name} hands-on simulation scenarios"),
            "price": meta.get("price", 499),
            "order": meta.get("order", 50),
            "coming_soon": meta.get("coming_soon", False),
            "is_active": meta.get("is_active", True),
        }
        slug = meta.get("slug")
        if slug:
            # 1. Try exact slug match first (idempotent updates)
            try:
                technology = Technology.objects.get(slug=slug)
                for k, v in {**defaults, "name": name}.items():
                    setattr(technology, k, v)
                technology.save()
                return technology
            except Technology.DoesNotExist:
                pass
            # 2. A record with the same name but old/different slug exists — migrate it
            try:
                technology = Technology.objects.get(name=name)
                technology.slug = slug
                for k, v in defaults.items():
                    setattr(technology, k, v)
                technology.save()
                return technology
            except Technology.DoesNotExist:
                pass
            # 3. Neither exists — create fresh
            return Technology.objects.create(slug=slug, name=name, **defaults)
        else:
            technology, _ = Technology.objects.update_or_create(
                name=name,
                defaults=defaults,
            )
            return technology

    def handle(self, *args, **options):
        scenarios_dir = options["dir"]
        tech_filter = {
            t.strip().lower()
            for t in (options.get("technologies") or "").split(",")
            if t.strip()
        }
        merge_only = bool(options.get("merge_only"))

        if not os.path.exists(scenarios_dir):
            scenarios_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                "..",
                "scenarios",
            )

        if not os.path.exists(scenarios_dir):
            self.stderr.write(self.style.ERROR(f"Scenarios directory not found: {scenarios_dir}"))
            return

        count = 0
        for tech_dir in sorted(os.listdir(scenarios_dir)):
            tech_path = os.path.join(scenarios_dir, tech_dir)
            if not os.path.isdir(tech_path):
                continue
            if tech_filter and tech_dir.lower() not in tech_filter:
                continue

            technology = self._load_technology(tech_dir, tech_path)

            for scenario_dir in sorted(os.listdir(tech_path)):
                yaml_path = os.path.join(tech_path, scenario_dir, "scenario.yaml")
                if not os.path.isfile(yaml_path):
                    continue

                with open(yaml_path) as f:
                    try:
                        data = yaml.safe_load(f)
                    except yaml.YAMLError as exc:
                        self.stderr.write(self.style.ERROR(f"Invalid YAML in {yaml_path}: {exc}"))
                        continue

                if not data:
                    self.stderr.write(self.style.WARNING(f"Skipping empty scenario: {yaml_path}"))
                    continue

                check_path = os.path.join(tech_path, scenario_dir, "check.sh")
                validation_script = ""
                if os.path.isfile(check_path):
                    with open(check_path) as f:
                        validation_script = f.read()

                service_path = os.path.join(tech_path, scenario_dir, "service.sh")
                cloud_setup = ""
                if os.path.isfile(service_path):
                    with open(service_path) as f:
                        cloud_setup = f.read()

                lab_mode = data.get("lab_mode", "docker")
                infra = data.get("infrastructure_type", "docker")
                if lab_mode == "simulation":
                    infra = "docker"  # valid choice; runtime uses lab_mode

                sim_type = data.get("simulation_type", "generic")
                from apps.labs.provisioner.simulation.sim_types import normalize_sim_type
                sim_type = normalize_sim_type(sim_type)

                slug = data.get("slug", scenario_dir)
                if merge_only and Scenario.objects.filter(slug=slug).exists():
                    Scenario.objects.filter(slug=slug).update(
                        lab_mode=lab_mode,
                        simulation_type=sim_type,
                        infrastructure_type=infra,
                    )
                    self.stdout.write(f"  Synced lab metadata: {slug} ({lab_mode}/{sim_type})")
                    continue

                scenario, created = Scenario.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "title": data["title"],
                        "technology": technology,
                        "category": data.get("category", "General"),
                        "difficulty": data.get("difficulty", "easy"),
                        "description": data.get("description", ""),
                        "objectives": data.get("objectives", []),
                        "initial_state": data.get("initial_state", ""),
                        "validation_script": validation_script,
                        "docker_image": f"fixitlab/scenario-{data.get('slug', scenario_dir)}:latest",
                        "time_limit": data.get("time_limit", 600),
                        "max_score": data.get("max_score", 100),
                        "is_active": True,
                        "is_free": data.get("is_free", False),
                        "infrastructure_type": infra,
                        "docker_privileged": data.get("docker_privileged", False),
                        "cloud_setup_script": data.get("cloud_setup_script", cloud_setup),
                        "cloud_image": data.get("cloud_image", "ubuntu-22-04-x64"),
                        "jira_priority": data.get("jira_priority", "Medium"),
                        "jira_issue_template": data.get("jira_issue_template", ""),
                        "blocked_commands": data.get("blocked_commands", []),
                        "lab_mode": lab_mode,
                        "simulation_type": sim_type,
                        "scenario_type": data.get("scenario_type", "fix"),
                        "requires_companion_hosts": data.get("requires_companion_hosts", False),
                        "dual_terminal": data.get("dual_terminal", False),
                        "coding_mode": data.get("coding_mode", False),
                        "coding_spec": data.get("coding_spec", {}) or {},
                        "cross_technology": data.get("cross_technology", False),
                        "vmware_link": data.get("vmware_link", False),
                        "certification_only": data.get("certification_only", False),
                        # ITSM (ServiceNow-style) ticket flow.
                        "itsm_enabled": data.get("itsm_enabled", False),
                        "itsm_ticket_type": data.get("itsm_ticket_type", "incident"),
                        "itsm_config": data.get("itsm_config", {}) or {},
                    },
                )

                for hint_data in data.get("hints", []):
                    Hint.objects.update_or_create(
                        scenario=scenario,
                        order=hint_data["order"],
                        defaults={
                            "content": hint_data["content"],
                            "penalty": hint_data.get("cost", 10),
                        },
                    )

                action = "Created" if created else "Updated"
                self.stdout.write(f"  {action}: {data['title']} [{technology.name}] ({lab_mode}/{sim_type})")
                count += 1

        self.stdout.write(self.style.SUCCESS(f"\nSeeded {count} scenarios successfully."))
        try:
            from apps.question_bank.cache_utils import invalidate_technologies_cache
            invalidate_technologies_cache()
        except Exception:
            pass
