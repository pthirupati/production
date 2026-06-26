"""Sync Technology.learning_path and Tutorial.scenario_slug from scenario catalog."""

from django.core.management.base import BaseCommand

from apps.question_bank.technology_catalog import sync_catalog


class Command(BaseCommand):
    help = "Link tutorials to scenarios and populate technology learning paths"

    def handle(self, *args, **options):
        sync_catalog(stdout=self.stdout, style=self.style)
