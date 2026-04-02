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


class Command(BaseCommand):
    help = "Seed the database with scenario definitions from YAML files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default="/scenarios",
            help="Root directory containing scenario YAML files",
        )

    def handle(self, *args, **options):
        scenarios_dir = options["dir"]

        # Also try relative path from project root
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

            # Get or create the technology
            technology, _ = Technology.objects.get_or_create(
                name=tech_dir.replace("-", " ").title(),
                defaults={"icon": "terminal", "description": f"{tech_dir.title()} troubleshooting scenarios"},
            )

            for scenario_dir in sorted(os.listdir(tech_path)):
                yaml_path = os.path.join(tech_path, scenario_dir, "scenario.yaml")
                if not os.path.isfile(yaml_path):
                    continue

                with open(yaml_path) as f:
                    data = yaml.safe_load(f)

                check_path = os.path.join(tech_path, scenario_dir, "check.sh")
                validation_script = ""
                if os.path.isfile(check_path):
                    with open(check_path) as f:
                        validation_script = f.read()

                scenario, created = Scenario.objects.update_or_create(
                    slug=data.get("slug", scenario_dir),
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
                        "time_limit": data.get("time_limit", 900),
                        "max_score": data.get("max_score", 100),
                        "is_active": True,
                    },
                )

                # Create hints
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
                self.stdout.write(f"  {action}: {data['title']}")
                count += 1

        self.stdout.write(self.style.SUCCESS(f"\nSeeded {count} scenarios successfully."))
