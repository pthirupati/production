"""`systemctl cat`/`show` must read the unit file, not synthesise it.

Both simulated shells wrote real unit files into the VFS and then never read
them back: `systemctl cat` built content from the unit NAME, so a learner who
edited ExecStart saw the edit via `cat /etc/systemd/system/x.service` but not
via `systemctl cat x` — a convincing lie rather than an honest error.
"""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_shell import RHELShell


class SystemctlCatReadsUnitFileTests(SimpleTestCase):
    def setUp(self):
        # This preset writes a real appstack.service with a docker-compose
        # ExecStart, so a synthesised unit is trivially distinguishable.
        self.shell = RHELShell(scenario_slug="docker-handoff-systemd-managed-stack")

    def test_cat_shows_on_disk_execstart(self):
        out = self.shell.run("systemctl cat appstack")
        self.assertIn("/usr/bin/docker compose", out)
        # The fabricated version claimed ExecStart=/usr/sbin/appstack.
        self.assertNotIn("/usr/sbin/appstack", out)

    def test_cat_reflects_an_edit(self):
        self.shell.state.write_file(
            "/etc/systemd/system/appstack.service",
            "[Unit]\nDescription=Containerized application stack\n\n"
            "[Service]\nType=oneshot\nExecStart=/usr/bin/true\n\n"
            "[Install]\nWantedBy=multi-user.target\n",
        )
        out = self.shell.run("systemctl cat appstack")
        self.assertIn("ExecStart=/usr/bin/true", out)
        self.assertNotIn("docker compose", out)

    def test_cat_names_the_path_it_read(self):
        out = self.shell.run("systemctl cat appstack")
        self.assertIn("# /etc/systemd/system/appstack.service", out)

    def test_cat_reports_missing_unit_instead_of_inventing_one(self):
        out = self.shell.run("systemctl cat definitelynotaunit")
        self.assertIn("No files found", out)

    def test_show_exposes_unit_file_properties(self):
        out = self.shell.run("systemctl show appstack")
        self.assertIn("Id=appstack.service", out)
        self.assertIn("/usr/bin/docker compose", out)

    def test_show_single_property(self):
        out = self.shell.run("systemctl show -p ActiveState appstack")
        self.assertEqual(out.strip(), "ActiveState=failed")


class SystemctlCatFallbackTests(SimpleTestCase):
    """Units with no file on disk still describe themselves honestly."""

    def setUp(self):
        self.shell = RHELShell(scenario_slug="sim-rhel-broken-nginx")

    def test_known_service_without_unit_file_is_still_catable(self):
        # sshd is a seeded service with no VFS unit file; cat should describe
        # it from service state rather than 404, but must not invent an
        # ExecStart that contradicts a file the learner could open.
        out = self.shell.run("systemctl cat sshd")
        self.assertIn("sshd.service", out)
        self.assertIn("[Service]", out)
