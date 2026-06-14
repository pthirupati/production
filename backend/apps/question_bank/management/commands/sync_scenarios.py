"""Sync scenario definitions from repo YAML/check.sh into the database."""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync scenarios from scenarios/ directory (alias for seed_scenarios with deploy-friendly output)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            default=None,
            help="Root directory containing scenario YAML files (default: repo scenarios/)",
        )

    def handle(self, *args, **options):
        kwargs = {}
        if options.get("dir"):
            kwargs["dir"] = options["dir"]
        self.stdout.write("Syncing scenarios from disk into database...")
        call_command("seed_scenarios", **kwargs)
        self.stdout.write(self.style.SUCCESS("Scenario sync complete."))
