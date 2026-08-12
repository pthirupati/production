"""Session 86 — optional voice stack adapters (env-gated)."""

from django.test import SimpleTestCase, override_settings
from unittest import mock
import os

from apps.interviews.services import voice_stack as vs


class VoiceStackAdapterTest(SimpleTestCase):
    def test_status_defaults_to_browser(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in (
                "FIXITLAB_PIPER_BIN",
                "FIXITLAB_INDICF5_URL",
                "FIXITLAB_FASTER_WHISPER_URL",
                "FIXITLAB_INDIC_WHISPER_URL",
                "FIXITLAB_LLM_GENERATE_URL",
            ):
                os.environ.pop(key, None)
            st = vs.voice_stack_status()
        self.assertEqual(st["default"], "simulation")
        self.assertFalse(st["piper"])
        self.assertTrue(st["llm_generate"])  # sim path counts as available
        self.assertTrue(st["llm_generate_sim"])

    def test_piper_returns_none_without_binary(self):
        with mock.patch.dict(os.environ, {"FIXITLAB_PIPER_BIN": "/no/such/piper"}, clear=False):
            self.assertIsNone(vs.synthesize_piper("hello"))

    def test_llm_generate_uses_simulation_without_url(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FIXITLAB_LLM_GENERATE_URL", None)
            out = vs.llm_generate_reply("sys", "Tell me about kubernetes")
        self.assertIsNotNone(out)
        self.assertIn("kubernetes", out.lower())
