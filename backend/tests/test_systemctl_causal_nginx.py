"""Bringing nginx up must be causal on the config, whichever verb the learner uses.

Config and service state were decoupled: the simulator started nginx regardless of
what `nginx -t` said, so a config lab could be "solved" without fixing anything.
`start` was then gated (audit §F1) — but only `start`. `restart`,
`reload-or-restart`, `try-restart` and `enable --now` still activated the unit
unconditionally, and *restart is the verb a learner actually types after editing a
file*. Any grader asserting `systemctl is-active nginx` passed a lab in which the
typo was still there.

The other half of the contract matters just as much: once the config IS fixed the
lab must be solvable by every one of those verbs. A gate that fails closed on
correct work is the BROKEN_FIX regression, not a fix.

`nginx-broken-config` ships a `listn` typo in /etc/nginx/sites-enabled/default —
these tests drive the real learner flow against it rather than hand-writing config.
"""
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_shell import RHELShell

SLUG = "nginx-broken-config"
FIX = "sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default"
BREAK = "sed -i 's/listen/listn/' /etc/nginx/sites-enabled/default"

ACTIVATING_VERBS = [
    "systemctl start nginx",
    "systemctl restart nginx",
    "systemctl reload-or-restart nginx",
    "systemctl try-restart nginx",
    "systemctl enable --now nginx",
]


class _Base(SimpleTestCase):
    def shell(self):
        return RHELShell(scenario_slug=SLUG)

    def active(self, sh):
        return sh.run("systemctl is-active nginx").strip()


class BrokenConfigRefusesToStartTests(_Base):
    def test_preset_really_ships_a_broken_config(self):
        """Guard the premise — if the preset stops breaking nginx these tests are
        vacuous and would pass while proving nothing."""
        sh = self.shell()
        self.assertNotIn("test is successful", sh.run("nginx -t"))

    def test_no_activating_verb_can_start_a_broken_nginx(self):
        for cmd in ACTIVATING_VERBS:
            with self.subTest(cmd=cmd):
                sh = self.shell()
                sh.run(cmd)
                self.assertNotEqual(
                    self.active(sh), "active",
                    f"`{cmd}` started nginx against a config `nginx -t` rejects — "
                    "the lab grades as solved with the typo still in place",
                )

    def test_failed_start_reports_like_systemd(self):
        sh = self.shell()
        out = sh.run("systemctl start nginx")
        self.assertIn("Job for nginx.service failed", out)
        self.assertIn("journalctl", out)
        self.assertEqual(sh.state.last_exit_code, 1)

    def test_failed_unit_shows_as_failed(self):
        sh = self.shell()
        sh.run("systemctl restart nginx")
        self.assertIn("failed", sh.run("systemctl status nginx").lower())


class FixedConfigStaysSolvableTests(_Base):
    def test_every_activating_verb_works_once_fixed(self):
        for cmd in ACTIVATING_VERBS:
            with self.subTest(cmd=cmd):
                sh = self.shell()
                sh.run(FIX)
                self.assertIn("test is successful", sh.run("nginx -t"))
                sh.run(cmd)
                self.assertEqual(
                    self.active(sh), "active",
                    f"`{cmd}` refused a VALID config — the lab is unsolvable",
                )

    def test_the_gate_does_not_clobber_the_learners_exit_code(self):
        """The gate shells out to `nginx -t` internally; that must not overwrite the
        $? a learner is about to inspect after their own successful command."""
        sh = self.shell()
        sh.run(FIX)
        sh.run("true")
        sh.run("systemctl start nginx")
        self.assertEqual(sh.state.last_exit_code, 0)


class ReloadKeepsServingOldConfigTests(_Base):
    """Real nginx tests the config before applying it, so a failed reload leaves the
    master process up on the OLD config. Treating reload like restart would take a
    healthy service down — worse than the bug being fixed."""

    def test_failed_reload_leaves_the_service_running(self):
        sh = self.shell()
        sh.run(FIX)
        sh.run("systemctl start nginx")
        self.assertEqual(self.active(sh), "active")

        sh.run(BREAK)
        out = sh.run("systemctl reload nginx")
        self.assertEqual(sh.state.last_exit_code, 1, "failed reload reported success")
        self.assertIn("failed", out.lower())
        self.assertEqual(
            self.active(sh), "active",
            "a failed reload stopped nginx — real nginx keeps serving the old config",
        )

    def test_reload_on_a_stopped_unit_still_reports_not_applicable(self):
        sh = self.shell()
        sh.run(FIX)
        out = sh.run("systemctl reload nginx")
        self.assertIn("not applicable", out)
        self.assertEqual(sh.state.last_exit_code, 5)


class OtherUnitsAreUnaffectedTests(_Base):
    """The gate is nginx-specific; it must not leak into unrelated services."""

    def test_sshd_starts_normally(self):
        sh = self.shell()
        sh.run("systemctl start sshd")
        self.assertEqual(sh.run("systemctl is-active sshd").strip(), "active")

    def test_restart_of_another_unit_is_unaffected(self):
        sh = self.shell()
        sh.run("systemctl restart sshd")
        self.assertEqual(sh.run("systemctl is-active sshd").strip(), "active")
