"""Re-apply topic-specific tutorial enrichment to all stored lesson bodies."""

from django.core.management.base import BaseCommand

from apps.tutorials.completeness import enrich_body
from apps.tutorials.models import TutorialSection
from apps.tutorials.tutorial_enrichment import strip_auto_enrichment, fix_broken_prose


class Command(BaseCommand):
    help = "Strip legacy generic enrichment blocks and re-apply topic-specific diagrams/commands."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count changes without saving")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        updated = 0
        for section in TutorialSection.objects.select_related("tutorial").iterator():
            topic = section.tutorial.topic or ""
            title = section.tutorial.title or ""
            raw = fix_broken_prose(strip_auto_enrichment(section.body or ""))
            new_body = enrich_body(topic, title, raw)
            if new_body != (section.body or ""):
                updated += 1
                if not dry:
                    section.body = new_body
                    section.save(update_fields=["body"])
        verb = "Would update" if dry else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {updated} tutorial sections"))
