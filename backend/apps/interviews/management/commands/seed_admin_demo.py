"""
Seed demo interview certificate and sample interview for admin testing.

Usage:
  python manage.py seed_admin_demo
  SUPERUSER_EMAIL=admin@example.com python manage.py seed_admin_demo
"""

import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = "Create demo interview certificate and sample interview for the platform admin"

    def handle(self, *args, **options):
        email = (os.environ.get("SUPERUSER_EMAIL") or "").strip().lower()
        user = None
        if email:
            user = User.objects.filter(email__iexact=email, is_staff=True).first()
        if not user:
            user = User.objects.filter(is_superuser=True).order_by("id").first()
        if not user:
            self.stderr.write(self.style.ERROR("No superuser found. Set SUPERUSER_EMAIL or create a superuser."))
            return

        from apps.question_bank.models import Technology
        from apps.interviews.models import (
            InterviewCampaign, InterviewCertificate, InterviewRound, InterviewPlanTier,
        )
        from apps.interviews.models import InterviewEntitlement

        tech, _ = Technology.objects.get_or_create(
            slug="linux-administration",
            defaults={"name": "Linux Administration", "is_active": True, "price": 499},
        )

        cert_id = "FIXIT-INT-ADMIN-DEMO-2026"
        campaign, created = InterviewCampaign.objects.get_or_create(
            user=user,
            title="Admin Demo Interview",
            defaults={
                "primary_technology": tech,
                "experience_level": "mid",
                "round_count": 3,
                "status": "completed",
                "overall_score": 88,
                "is_sample": False,
            },
        )
        if not created:
            campaign.status = "completed"
            campaign.overall_score = 88
            campaign.save(update_fields=["status", "overall_score"])

        cert, cert_created = InterviewCertificate.objects.update_or_create(
            certificate_id=cert_id,
            defaults={
                "campaign": campaign,
                "user": user,
                "holder_name": user.get_full_name() or user.username,
                "technology_name": tech.name,
                "level": "mid",
                "rounds_cleared": 3,
                "overall_score": 88,
                "expires_at": timezone.now() + timedelta(days=365),
                "linkedin_share_text": f"Verify my FixitLab demo certificate: {cert_id}",
            },
        )

        tier, _ = InterviewPlanTier.objects.get_or_create(
            code="admin-demo",
            defaults={"name": "Admin Demo", "price_inr": 0, "certificate_enabled": True},
        )

        sample_campaign = InterviewCampaign.objects.filter(user=user, is_sample=True).first()
        if not sample_campaign:
            sample_campaign = InterviewCampaign.objects.create(
                user=user,
                title="Admin Sample Interview",
                primary_technology=tech,
                experience_level="junior",
                round_count=1,
                status="draft",
                is_sample=True,
            )
            InterviewRound.objects.get_or_create(
                campaign=sample_campaign,
                round_number=1,
                defaults={
                    "title": "Sample voice round",
                    "duration_minutes": 10,
                    "status": "scheduled",
                },
            )
        ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
        ent.sample_interview_used = False
        ent.save(update_fields=["sample_interview_used"])

        self.stdout.write(self.style.SUCCESS(
            f"Admin demo ready for {user.email}:\n"
            f"  Certificate: {cert.certificate_id} ({'created' if cert_created else 'updated'})\n"
            f"  Verify: /verify-certificate?certificate_id={cert_id}\n"
            f"  Sample interview campaign id={sample_campaign.id}"
        ))
