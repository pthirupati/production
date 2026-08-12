"""Session 90 — cache authority, whisper prompt, secrets expand, LLM URL normalize."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import shell as sim_shell
from apps.interviews.services import voice_stack as vs


class CacheAuthorityRefreshTest(SimpleTestCase):
    def setUp(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()

    def tearDown(self):
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()

    def test_local_hit_refreshes_when_cache_newer(self):
        old = mock.Mock(name="old-engine")
        new = mock.Mock(name="new-engine")
        new.simulation_type = "linux"
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS["auth-1"] = {
                "resource_id": "r",
                "sim_type": "linux",
                "state": {"engine": old},
                "streams": {},
                "last_access": 1.0,
                "engine_mutated_at": 10.0,
            }
        snap = {"version": 1, "mutated_at": 20.0}
        with mock.patch.dict(os.environ, {"SIM_ENGINE_CACHE_AUTHORITY": "1"}):
            with mock.patch(
                "apps.labs.provisioner.simulation.sim_persistence.cache_get_snapshot",
                return_value=snap,
            ):
                with mock.patch(
                    "apps.labs.provisioner.simulation.sim_persistence.restore_engine",
                    return_value=new,
                ):
                    entry = sim_shell.get_sim_session("auth-1")
        self.assertIs(entry["state"]["engine"], new)
        self.assertEqual(entry["engine_mutated_at"], 20.0)

    def test_authority_disabled_keeps_local(self):
        old = mock.Mock(name="old")
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS["auth-off"] = {
                "resource_id": "r",
                "sim_type": "linux",
                "state": {"engine": old},
                "streams": {},
                "last_access": 1.0,
                "engine_mutated_at": 10.0,
            }
        with mock.patch.dict(os.environ, {"SIM_ENGINE_CACHE_AUTHORITY": "0"}):
            with mock.patch(
                "apps.labs.provisioner.simulation.sim_persistence.cache_get_snapshot"
            ) as get:
                entry = sim_shell.get_sim_session("auth-off")
        self.assertIs(entry["state"]["engine"], old)
        get.assert_not_called()


class VoiceStackS90Test(SimpleTestCase):
    def test_domain_vocab_includes_tech_tokens(self):
        p = vs.domain_vocab_prompt()
        self.assertIn("kubernetes", p)
        self.assertTrue(len(p) > 20)

    def test_normalize_chat_url(self):
        self.assertTrue(vs._normalize_chat_url("http://h:8080").endswith("/v1/chat/completions"))
        self.assertEqual(
            vs._normalize_chat_url("http://h/v1/chat/completions"),
            "http://h/v1/chat/completions",
        )

    def test_whisper_openai_url_normalize(self):
        self.assertTrue(
            vs._normalize_whisper_openai_url("http://h:8001").endswith("/v1/audio/transcriptions")
        )

    def test_llm_probe_uses_simulation_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FIXITLAB_LLM_GENERATE_URL", None)
            out = vs.llm_probe()
        self.assertTrue(out["ok"])
        self.assertTrue(out.get("simulation"))

    def test_sim_llm_normalizes_question(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FIXITLAB_LLM_GENERATE_URL", None)
            text = vs.llm_generate_reply(
                "You are rewriting a question",
                "  Walk me through your **rollback** plan  ",
            )
        self.assertIsNotNone(text)
        self.assertTrue(text.endswith("?"))
        self.assertNotIn("**", text)

    def test_status_marks_sim_providers(self):
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
        self.assertTrue(st["simulation"])
        self.assertTrue(st["llm_generate_sim"])
        self.assertTrue(st["piper_sim"])
        self.assertTrue(st["faster_whisper_sim"])


class SecretsVerifyExpandTest(SimpleTestCase):
    def test_fails_on_guest_broker(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_secrets_rotated.py"
        env = {k: v for k, v in os.environ.items() if k not in (
            "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "RAZORPAY_KEY_SECRET",
            "CELERY_BROKER_URL",
        )}
        env["SECRET_KEY"] = "prod-rotated-key-not-django-insecure"
        env["CELERY_BROKER_URL"] = "amqp://guest:guest@localhost:5672//"
        proc = subprocess.run(
            [sys.executable, str(script)],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("CELERY_BROKER_URL", proc.stderr)
