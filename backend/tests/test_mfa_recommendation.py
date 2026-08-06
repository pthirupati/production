"""Audit Z2-3 — who gets *asked* to turn MFA on.

Mandating TOTP for every learner would cost more signups than it protects: a
typical account holds course progress and a Rs 499 subscription.

But this platform is not typical. The AI Interview Studio stores resumes,
interview transcripts, `current_company` and `current_package_lpa`, so a
compromised account there leaks that a named person is job-hunting and what they
currently earn. That is materially more sensitive than which Kubernetes lab
someone finished — and it is attached to ordinary, non-staff accounts.

So the split is not "learner versus admin". It is **how much of this person's data
is actually sensitive**. Those users are asked; nobody is blocked.

Two things make this a nudge rather than a nag, and both are tested:

* it is snoozed for 30 days once dismissed. A prompt that returns on every login
  is one people learn to click past without reading, which also trains them to
  dismiss the next real warning;
* an *empty* CandidateProfile does not count. The row is created as soon as
  someone opens the interview section, so keying on "has a profile" would prompt
  people who have entered nothing.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.mfa_models import (
    MFA_PROMPT_SNOOZE_DAYS,
    MfaDevice,
    mfa_recommended_for,
)
from apps.accounts.models import Profile
from apps.interviews.models import CandidateProfile, InterviewCampaign

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


class _Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rec", email="rec@example.com", password=PASSWORD
        )
        Profile.objects.get_or_create(user=self.user)
        self.client = APIClient()

    def _with_resume(self):
        CandidateProfile.objects.create(user=self.user, resume_text="Ten years of Linux.")
        self.user.refresh_from_db()


class WhoGetsAskedTests(_Base):
    def test_a_plain_learner_is_not_prompted(self):
        """Course progress alone does not justify interrupting a sign-in."""
        self.assertFalse(mfa_recommended_for(self.user))

    def test_someone_with_a_resume_is_prompted(self):
        self._with_resume()
        self.assertTrue(mfa_recommended_for(self.user))

    def test_current_package_alone_is_enough(self):
        """Salary is among the most sensitive fields on the platform."""
        CandidateProfile.objects.create(
            user=self.user, current_package_lpa=Decimal("24.50")
        )
        self.user.refresh_from_db()
        self.assertTrue(mfa_recommended_for(self.user))

    def test_an_interview_campaign_alone_is_enough(self):
        """Transcripts live under the campaign, not the candidate profile."""
        InterviewCampaign.objects.create(user=self.user)
        self.assertTrue(mfa_recommended_for(self.user))

    def test_an_empty_candidate_profile_does_not_count(self):
        """The row is created as soon as someone opens the interview section, so
        keying on its existence would prompt people who entered nothing."""
        CandidateProfile.objects.create(user=self.user)
        self.user.refresh_from_db()
        self.assertFalse(
            mfa_recommended_for(self.user),
            "an empty CandidateProfile triggered the prompt",
        )

    def test_someone_who_already_has_mfa_is_not_prompted(self):
        self._with_resume()
        MfaDevice.objects.create(
            user=self.user, secret=MfaDevice.new_secret(), enabled=True
        )
        self.user.refresh_from_db()
        self.assertFalse(mfa_recommended_for(self.user))

    def test_a_pending_unconfirmed_device_still_prompts(self):
        """Starting setup and abandoning it leaves the account unprotected."""
        self._with_resume()
        MfaDevice.objects.create(
            user=self.user, secret=MfaDevice.new_secret(), enabled=False
        )
        self.user.refresh_from_db()
        self.assertTrue(mfa_recommended_for(self.user))

    def test_staff_are_not_recommended_they_are_required(self):
        """Two different messages; showing both would be contradictory."""
        self._with_resume()
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.assertFalse(mfa_recommended_for(self.user))

    def test_an_anonymous_user_is_not_prompted(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(mfa_recommended_for(AnonymousUser()))


class ItIsANudgeNotANagTests(_Base):
    def setUp(self):
        super().setUp()
        self._with_resume()
        self.client.force_authenticate(user=self.user)

    def test_dismissing_stops_the_prompt(self):
        resp = self.client.post("/api/auth/mfa/dismiss-prompt/", {}, format="json")
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.user.refresh_from_db()
        self.assertFalse(mfa_recommended_for(self.user))

    def test_the_dismissal_expires(self):
        """Someone who uploaded a resume months ago should be asked again."""
        self.client.post("/api/auth/mfa/dismiss-prompt/", {}, format="json")
        Profile.objects.filter(user=self.user).update(
            mfa_prompt_dismissed_at=timezone.now()
            - timedelta(days=MFA_PROMPT_SNOOZE_DAYS + 1)
        )
        self.user.refresh_from_db()
        self.assertTrue(mfa_recommended_for(self.user))

    def test_the_snooze_is_long_enough_to_not_be_a_nag(self):
        self.assertGreaterEqual(
            MFA_PROMPT_SNOOZE_DAYS, 14,
            "a short snooze makes this a prompt people click past without reading",
        )

    def test_dismissing_requires_authentication(self):
        anon = APIClient()
        resp = anon.post("/api/auth/mfa/dismiss-prompt/", {}, format="json")
        self.assertIn(resp.status_code, (401, 403))

    def test_the_route_is_wired(self):
        from django.urls import resolve

        self.assertEqual(
            resolve("/api/auth/mfa/dismiss-prompt/").func.view_class.__name__,
            "MfaDismissPromptView",
        )


class TheApiSurfacesItTests(_Base):
    def test_login_reports_the_recommendation(self):
        self._with_resume()
        resp = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": PASSWORD}, format="json",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.assertTrue(resp.data["mfa_recommended"])

    def test_login_does_not_block(self):
        """The whole point: recommended, never required."""
        self._with_resume()
        resp = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": PASSWORD}, format="json",
        )
        self.assertIn(
            "access", resp.data,
            "a recommendation blocked the login — that is a requirement, not a nudge",
        )

    def test_a_plain_learner_login_does_not_recommend(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": PASSWORD}, format="json",
        )
        self.assertFalse(resp.data["mfa_recommended"])

    def test_the_profile_reports_it_too(self):
        """The login response is seen once; the profile is what a settings page
        reads on every visit."""
        self._with_resume()
        self.client.force_authenticate(user=self.user)
        data = self.client.get("/api/auth/profile/").data
        self.assertTrue(data["mfa_recommended"])
        self.assertFalse(data["mfa_enabled"])
