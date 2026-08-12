"""Smoke test for scripts/ci-wire-cluster-env.py (audit O5 EDGE_BIND_IP)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WIRE = REPO_ROOT / "scripts" / "ci-wire-cluster-env.py"


class WireClusterEnvTests(unittest.TestCase):
    def test_writes_edge_bind_ip_from_edge_private_ip(self):
        env_body = (
            "REDIS_PASSWORD=secret\n"
            "CELERY_BROKER_URL=amqp://u:p@old:5672//\n"
            "CELERY_RESULT_BACKEND=redis://:secret@old:6379/2\n"
            "DJANGO_ALLOWED_HOSTS=localhost\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env.cluster"
            path.write_text(env_body, encoding="utf-8")
            env = os.environ.copy()
            env.update(
                {
                    "EDGE_PRIVATE_IP": "10.1.0.1",
                    "APP_PRIVATE_IP": "10.1.0.2",
                    "DATA_PRIVATE_IP": "10.1.0.3",
                    "LABS_PRIVATE_IP": "10.1.0.4",
                }
            )
            # Clear DRY_RUN if set in the parent environment.
            env.pop("DRY_RUN", None)
            proc = subprocess.run(
                ["python3", str(WIRE), "--file", str(path)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = path.read_text(encoding="utf-8")
            self.assertIn("EDGE_BIND_IP=10.1.0.1", text)
            self.assertIn("VAULT_ADDR=http://10.1.0.1:8200", text)
            self.assertIn("REDIS_HOST=10.1.0.1", text)


if __name__ == "__main__":
    unittest.main()
