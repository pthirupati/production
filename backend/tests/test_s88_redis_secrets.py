"""Session 88 — Redis eviction flushes cache; secrets verify script."""

from django.test import SimpleTestCase
from unittest import mock
import os
import subprocess
import sys
from pathlib import Path

from apps.labs.provisioner.simulation import shell as sim_shell


class RedisEvictionCacheFlushTest(SimpleTestCase):
    def test_cache_put_called_before_idle_eviction(self):
        engine = object()
        sid = "sess-evict-1"
        with sim_shell._SIM_LOCK:
            sim_shell._SIM_SESSIONS.clear()
            sim_shell._SIM_SESSIONS[sid] = {
                "last_access": 0,  # ancient → idle
                "resource_id": "r1",
                "sim_type": "linux",
                "state": {"engine": engine},
                "streams": {},
            }
        with mock.patch(
            "apps.labs.provisioner.simulation.sim_persistence.cache_put_engine_snapshot"
        ) as put:
            with sim_shell._SIM_LOCK:
                n = sim_shell._evict_idle_locked()
        self.assertEqual(n, 1)
        put.assert_called_once()
        self.assertEqual(put.call_args.args[0], sid)


class SecretsVerifyScriptTest(SimpleTestCase):
    def test_script_passes_clean_env(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_secrets_rotated.py"
        env = {k: v for k, v in os.environ.items() if k not in (
            "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "RAZORPAY_KEY_SECRET",
        )}
        env["SECRET_KEY"] = "prod-rotated-key-not-django-insecure"
        proc = subprocess.run(
            [sys.executable, str(script)],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_script_fails_on_django_insecure(self):
        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_secrets_rotated.py"
        env = dict(os.environ)
        env["SECRET_KEY"] = "django-insecure-still-here"
        proc = subprocess.run(
            [sys.executable, str(script)],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("SECRET_KEY", proc.stderr)
