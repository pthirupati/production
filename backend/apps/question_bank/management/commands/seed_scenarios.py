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
    "linux": {"name": "Linux Administration", "icon": "terminal", "color": "cyan", "order": 5},
    "networking": {"name": "Networking", "icon": "globe", "color": "blue", "order": 7},
    "vmware": {"name": "VMware vSphere", "icon": "server", "color": "blue", "order": 8},
    "database": {"name": "Database Administration", "icon": "database", "color": "blue", "order": 10},
    "docker": {"name": "Docker & Containers", "icon": "container", "color": "cyan", "order": 11},
    "ansible": {"name": "Ansible Automation", "icon": "network", "color": "purple", "order": 12},
    "kubernetes": {"name": "Kubernetes", "icon": "layers", "color": "indigo", "order": 13},
    "baremetal": {"name": "Bare Metal & IPMI", "icon": "server", "color": "orange", "order": 14},
    "gpu": {"name": "GPU & NVIDIA", "icon": "cpu", "color": "green", "order": 15},
    "python": {"name": "Python Development", "icon": "code", "color": "yellow", "order": 16},
    "java": {"name": "Java Development", "icon": "code", "color": "orange", "order": 17},
    "html": {"name": "HTML & Web Servers", "icon": "globe", "color": "pink", "order": 18},
    "shell-script": {"name": "Shell Scripting", "icon": "terminal", "color": "teal", "order": 19},
    "devops": {"name": "DevOps", "icon": "layers", "color": "purple", "order": 20},
    "security": {"name": "Security", "icon": "shield", "color": "red", "order": 21},
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
        if meta.get("slug"):
            technology, _ = Technology.objects.update_or_create(
                slug=meta["slug"],
                defaults={**defaults, "name": name},
            )
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
                    self.stdout.write(f"  Skipped (exists): {slug}")
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
