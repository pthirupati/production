"""Fail-CLOSED grading tests for the Docker mounted-secret scenario.

The audit (docs/AUDIT_2026_08_TODO.md:2159) flagged that the leak surface existed
— `docker inspect` deep-copies the env list, `docker exec <c> env` prints it — but
the remediation target did not: `secrets` rows were name-only cosmetics with no
value and no mount, so a learner had nowhere to move the credential to.

The named risk was that a half-built scenario grades only "the env var is gone",
which passes someone who deleted the credential and broke the container. These
tests pin both halves of the contract:

  * fresh session FAILS (the credential is still in env) — never auto-pass
  * deleting the env var alone FAILS (workload can no longer resolve it)
  * renaming the env var FAILS (the leak moved, it did not close)
  * mounting a decoy value FAILS (mount exists, credential is wrong)
  * mount + env removal PASSES, and only then
  * removing the secret out from under a live mount FAILS again

Sessions use plain string ids so the engine runs purely on the Django cache.
"""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import docker_engine as de

SLUG = "docker-secrets-in-env"


class DockerSecretMountTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _fresh(self):
        sid = "test-docker-secret"
        de.drop_session(sid)
        de.get_state(sid, SLUG)  # seeds the scenario preset
        return sid

    def _mount(self, sid):
        return de.apply_action(sid, "mount_secret", {
            "container": de.LEAKED_SECRET_CONTAINER, "secret": de.LEAKED_SECRET_NAME,
        })

    def _unset_env(self, sid, key):
        return de.apply_action(sid, "remove_container_env", {
            "container": de.LEAKED_SECRET_CONTAINER, "key": key,
        })

    def _clear_leak(self, sid):
        self._unset_env(sid, de.LEAKED_SECRET_ENV)
        self._unset_env(sid, "DATABASE_URL")

    # ---- the fault is really planted ---------------------------------------
    def test_fresh_session_leaks_credential_and_fails_closed(self):
        sid = self._fresh()
        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertFalse(ok, f"must fail before the fix, got: {reason}")

        # The credential is observable through both leak surfaces.
        insp = de.apply_action(sid, "inspect_container", {"name": de.LEAKED_SECRET_CONTAINER})
        self.assertTrue(any(de.LEAKED_DB_PASSWORD in e for e in insp["inspect"]["env"]),
                        "docker inspect must expose the plaintext credential")
        ex = de.apply_action(sid, "exec_container",
                             {"container": de.LEAKED_SECRET_CONTAINER, "cmd": "env"})
        self.assertIn(de.LEAKED_DB_PASSWORD, ex["output"])

    # ---- the trap the audit warned about -----------------------------------
    def test_deleting_env_var_alone_does_not_pass(self):
        """A learner who deletes the credential has broken the container."""
        sid = self._fresh()
        self._clear_leak(sid)

        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertFalse(ok, "removing the env var without mounting must NOT pass")
        self.assertIn("mount secret", reason.lower())

    def test_renaming_the_env_var_does_not_pass(self):
        """Moving the leak to a differently-named key is not closing it."""
        sid = self._fresh()
        self._clear_leak(sid)
        c = de._find_container(de._load_session(sid)["state"], de.LEAKED_SECRET_CONTAINER)
        entry = de._load_session(sid)
        de._find_container(entry["state"], de.LEAKED_SECRET_CONTAINER)["env"].append(
            f"DB_PASS_2={de.LEAKED_DB_PASSWORD}"
        )
        de._save_session(sid, entry)
        self.assertIsNotNone(c)

        self._mount(sid)
        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertFalse(ok, "the credential is still readable via inspect under a new key")
        self.assertIn("DB_PASS_2", reason)

    def test_mounting_a_decoy_value_does_not_pass(self):
        """The mount must carry the working credential, not a placeholder."""
        sid = self._fresh()
        self._clear_leak(sid)
        res = de.apply_action(sid, "create_secret", {"name": "decoy_pw", "value": "placeholder"})
        self.assertTrue(res["ok"])
        res = de.apply_action(sid, "mount_secret", {
            "container": de.LEAKED_SECRET_CONTAINER, "secret": "decoy_pw",
        })
        self.assertTrue(res["ok"])

        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertFalse(ok, "mounting an unrelated secret must not satisfy the check")
        self.assertIn(de.LEAKED_SECRET_NAME, reason)

    # ---- the real fix ------------------------------------------------------
    def test_mount_plus_env_removal_passes(self):
        sid = self._fresh()
        res = self._mount(sid)
        self.assertTrue(res["ok"], res)

        # Mounting alone is not enough — the env var still leaks.
        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertFalse(ok, "mount without removing the env var must not pass")
        self.assertIn("docker inspect", reason)

        self._clear_leak(sid)
        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertTrue(ok, f"mount + env removal should pass, got: {reason}")

    def test_after_fix_credential_resolves_from_mount_but_not_from_inspect(self):
        """The asymmetry that is the whole lesson: readable inside, not outside."""
        sid = self._fresh()
        self._mount(sid)
        self._clear_leak(sid)

        insp = de.apply_action(sid, "inspect_container", {"name": de.LEAKED_SECRET_CONTAINER})
        self.assertFalse(any(de.LEAKED_DB_PASSWORD in e for e in insp["inspect"]["env"]),
                         "inspect must no longer reveal the credential")
        self.assertEqual(insp["inspect"]["secrets"][0]["secret"], de.LEAKED_SECRET_NAME)
        self.assertNotIn(de.LEAKED_DB_PASSWORD, str(insp["inspect"]["secrets"]))

        # But the container still resolves it from the tmpfs mount.
        ex = de.apply_action(sid, "exec_container", {
            "container": de.LEAKED_SECRET_CONTAINER,
            "cmd": f"cat {de._mounted_secret_path(de.LEAKED_SECRET_NAME)}",
        })
        self.assertEqual(ex["output"], de.LEAKED_DB_PASSWORD)
        self.assertEqual(ex["exitCode"], 0)

    def test_removing_the_secret_after_mounting_regresses_to_fail(self):
        """Deleting the mounted secret breaks the workload; grading must notice."""
        sid = self._fresh()
        self._mount(sid)
        self._clear_leak(sid)
        ok, _ = de.validate_docker_lab(sid, SLUG)
        self.assertTrue(ok)

        # Docker refuses to delete a secret still in use.
        res = de.apply_action(sid, "remove_secret", {"name": de.LEAKED_SECRET_NAME})
        self.assertFalse(res["ok"])
        self.assertIn("in use", res["error"])

        # Force the broken end-state: unmount, then delete.
        self.assertTrue(de.apply_action(sid, "unmount_secret", {
            "container": de.LEAKED_SECRET_CONTAINER, "secret": de.LEAKED_SECRET_NAME,
        })["ok"])
        self.assertTrue(de.apply_action(sid, "remove_secret", {"name": de.LEAKED_SECRET_NAME})["ok"])

        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertFalse(ok, "a container with no way to resolve the credential is broken")
        self.assertIn("does not exist", reason)

    def test_stopping_the_container_does_not_pass(self):
        """Least-effort cheat: stop the container so nothing leaks."""
        sid = self._fresh()
        self._mount(sid)
        self._clear_leak(sid)
        self.assertTrue(de.apply_action(sid, "stop_container",
                                        {"name": de.LEAKED_SECRET_CONTAINER})["ok"])

        ok, reason = de.validate_docker_lab(sid, SLUG)
        self.assertFalse(ok, "a stopped container is not a fixed container")
        self.assertIn("must be running", reason)

    # ---- engine contract ---------------------------------------------------
    def test_secret_values_never_reach_the_state_payload(self):
        sid = self._fresh()
        state = de.get_state(sid, SLUG)
        secrets = state["daemon"]["secrets"]
        self.assertTrue(any(s["name"] == de.LEAKED_SECRET_NAME for s in secrets))
        self.assertNotIn(de.LEAKED_DB_PASSWORD, str(secrets),
                         "the console payload must never carry secret plaintext")
        # Redaction is on a copy: the live session still resolves the real value.
        ex = de.apply_action(sid, "exec_container", {
            "container": de.LEAKED_SECRET_CONTAINER, "cmd": "cat /run/secrets/api_db_password",
        })
        self.assertEqual(ex["exitCode"], 1, "not mounted yet, so the path must not exist")
        self._mount(sid)
        de.get_state(sid, SLUG)  # a redacting read must not corrupt stored state
        ex = de.apply_action(sid, "exec_container", {
            "container": de.LEAKED_SECRET_CONTAINER, "cmd": "cat /run/secrets/api_db_password",
        })
        self.assertEqual(ex["output"], de.LEAKED_DB_PASSWORD)

    def test_create_secret_requires_a_value(self):
        """The v2 facade recorded name-only rows; a valueless secret is ungradeable."""
        sid = self._fresh()
        res = de.apply_action(sid, "create_secret", {"name": "no_value_here"})
        self.assertFalse(res["ok"])
        self.assertIn("value is required", res["error"])

    def test_unrelated_scenario_still_uses_the_worker_rule(self):
        """The new preset branch must not capture other docker slugs."""
        sid = "test-docker-oom"
        de.drop_session(sid)
        de.get_state(sid, "docker-memory-limit-oom")
        ok, reason = de.validate_docker_lab(sid, "docker-memory-limit-oom")
        self.assertFalse(ok)
        self.assertIn("cache", reason)
