"""Session 87 — TTS/STT voice_stack wiring + interview consent gate."""

from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from unittest import mock
import os
import base64

from apps.interviews.services import tts_service, stt_service
from apps.accounts.models import Profile


class TtsSttWiringTest(SimpleTestCase):
    def test_tts_defaults_browser(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("FIXITLAB_PIPER_BIN", "FIXITLAB_PIPER_VOICE", "FIXITLAB_INDICF5_URL"):
                os.environ.pop(k, None)
            cfg = tts_service.tts_config_for_frontend()
            self.assertEqual(cfg["tts_provider"], "browser_sim")
            self.assertTrue(cfg.get("simulation"))
            self.assertFalse(cfg["uses_server_tts"])
            res = tts_service.synthesize("hello")
            self.assertTrue(res.use_browser)
            self.assertEqual(res.provider, "browser_sim")

    def test_stt_faster_whisper_when_url_set(self):
        with mock.patch.dict(os.environ, {"FIXITLAB_FASTER_WHISPER_URL": "http://example.test/asr"}):
            with mock.patch(
                "apps.interviews.services.voice_stack.transcribe_faster_whisper",
                return_value={"text": "hello world", "avg_logprob": -0.2, "no_speech_prob": 0.01},
            ):
                out = stt_service.transcribe_audio(b"fakewav", language="en")
        self.assertEqual(out["provider"], "faster_whisper")
        self.assertEqual(out["transcript"], "hello world")
        self.assertGreater(out["confidence"], 0.5)

    def test_stt_config_exposes_server_when_whisper_url(self):
        with mock.patch.dict(os.environ, {"FIXITLAB_FASTER_WHISPER_URL": "http://example.test/asr"}):
            cfg = stt_service.stt_config_for_frontend()
        self.assertTrue(cfg["uses_server_stt"])
        self.assertEqual(cfg["stt_provider"], "faster_whisper")


User = get_user_model()


class InterviewConsentGateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("consent_user", "c@example.com", "pass12345")
        Profile.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_profile_exposes_and_updates_interview_consent(self):
        resp = self.client.get("/api/auth/profile/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("interview_processing_consent", True))

        resp = self.client.put(
            "/api/auth/profile/",
            {"interview_processing_consent": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["interview_processing_consent"])
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.interview_processing_consent)
