"""The grader-integrity gate must notice a lab that grades the wrong subject.

Two blind spots sit *behind* the fail-open scanner, and both are invisible to it
precisely because the graders involved fail-CLOSE correctly:

  * Topic incoherence (§G3). `academy-grafana-001-learn-datasources` is graded by
    `systemctl is-active rsyslog`. rsyslog IS down on the unfixed state, so the
    grader fail-closes, the scan says FAIL-CLOSED, and the gate prints PASS — while
    the lab can be solved without ever touching Grafana. Measured over the tree:
    1851 scenarios carry a `tasks[].validation.command` and 438 are incoherent.

  * Checker duplication (§G1/§G4). aws ships 420 academy labs behind ONE
    byte-identical check.sh. Whatever it asserts, 419 of those labs are not graded
    on their own subject, and the shared checker fail-closes so all 420 pass.

These tests pin both rules, and — more importantly — pin the false-positive traps
that make the naive versions unshippable. The naive coherence rule (technology slug
must appear as a substring of the command) flags 1314 of 1851 scenarios, and most
of those are correct: `nvidia-smi` is the right way to grade a `gpu` lab. A rule
that cries wolf on 1300 scenarios gets disabled within a week, which is how the
gate it was meant to backstop failed in the first place.
"""
import functools
import importlib.util
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

_SCRIPT = Path(settings.BASE_DIR).parent / "scripts" / "scan_grader_integrity.py"


def _load():
    spec = importlib.util.spec_from_file_location("_sgi_topic_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_sgi = _load()


class TopicCoherenceRuleTests(SimpleTestCase):
    """The rule itself, on hand-built inputs (no tree walk)."""

    def test_grafana_graded_by_rsyslog_is_incoherent(self):
        """The exact shape of all 100 academy-grafana labs."""
        self.assertIs(
            _sgi.is_topic_coherent("grafana", ["systemctl is-active rsyslog"]), False
        )

    def test_prometheus_graded_by_nginx_is_incoherent(self):
        self.assertIs(
            _sgi.is_topic_coherent("prometheus", ["systemctl is-active nginx"]), False
        )

    def test_sqlite_graded_by_postgresql_is_incoherent(self):
        """Adjacent technology is still the wrong technology."""
        self.assertIs(
            _sgi.is_topic_coherent("sqlite", ["systemctl is-active postgresql"]), False
        )

    def test_technology_named_in_the_command_is_coherent(self):
        self.assertIs(
            _sgi.is_topic_coherent("grafana", ["systemctl is-active grafana-server"]),
            True,
        )

    # ── False-positive traps: the naive substring rule fails every one of these ──

    def test_gpu_graded_by_nvidia_smi_is_coherent(self):
        """172 gpu labs. 'nvidia-smi' shares no substring with 'gpu' and is correct."""
        self.assertIs(_sgi.is_topic_coherent("gpu", ["nvidia-smi"]), True)

    def test_security_graded_by_sshd_is_coherent(self):
        """109 security labs grade ssh hardening via sshd. Correct, not incoherent."""
        self.assertIs(
            _sgi.is_topic_coherent("security", ["systemctl is-active sshd"]), True
        )

    def test_rhel_linux_graded_by_systemctl_is_coherent(self):
        """148 rhel-linux labs. systemd IS the subject of a RHEL lab."""
        self.assertIs(
            _sgi.is_topic_coherent("rhel-linux", ["systemctl is-active rsyslog"]), True
        )

    def test_database_graded_by_psql_is_coherent(self):
        self.assertIs(_sgi.is_topic_coherent("database", ["pg_isready"]), True)

    def test_database_graded_by_any_engine_is_coherent(self):
        """db-cassandra-down / db-clickhouse-down: engine names, not the word 'database'."""
        for cmd in (
            "systemctl is-active cassandra",
            "systemctl is-active clickhouse-server",
            "systemctl is-active elasticsearch",
        ):
            self.assertIs(_sgi.is_topic_coherent("database", [cmd]), True, cmd)

    # ── "Not assessed" must never read as "failed" ──

    def test_unmapped_technology_is_not_judged(self):
        """A technology nobody has characterised must not manufacture a failure."""
        self.assertIsNone(
            _sgi.is_topic_coherent("some-brand-new-tech", ["systemctl is-active nginx"])
        )

    def test_no_command_is_not_judged(self):
        self.assertIsNone(_sgi.is_topic_coherent("grafana", []))
        self.assertIsNone(_sgi.is_topic_coherent("grafana", [""]))

    def test_any_task_naming_the_technology_makes_it_coherent(self):
        """Multi-task labs are coherent if the subject is graded anywhere."""
        cmds = ["systemctl is-active nginx", "promtool check config /etc/prom.yml"]
        self.assertIs(_sgi.is_topic_coherent("prometheus", cmds), True)


class TopicCoherenceRatchetTests(SimpleTestCase):
    """The rule against the real tree, gated by a ceiling that may only shrink."""

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def _scan():
        """Walk the 7k-file scenario tree once — it is seconds per pass."""
        incoherent = []
        assessed = 0
        for slug, tech, commands in _sgi._iter_topics_from_fs():
            verdict = _sgi.is_topic_coherent(tech, commands)
            if verdict is None:
                continue
            assessed += 1
            if not verdict:
                incoherent.append((slug, tech, commands[0][:80]))
        return assessed, incoherent

    def test_incoherent_count_does_not_grow(self):
        assessed, incoherent = self._scan()
        self.assertGreater(assessed, 500, "coherence rule assessed almost nothing")
        self.assertLessEqual(
            len(incoherent),
            _sgi._TOPIC_INCOHERENT_CEILING,
            "New topic-incoherent scenarios: these grade a service unrelated to "
            "their own technology. Examples: "
            + "; ".join(f"{s} [{t}] -> {c}" for s, t, c in incoherent[:5]),
        )

    def test_rule_is_not_vacuous(self):
        """A rule that flags nothing passes forever and backstops nothing.

        The failure mode of the scanner this rule exists to reinforce was exactly
        this: it reported PASS because it never evaluated the labs in question.
        """
        _assessed, incoherent = self._scan()
        self.assertGreater(
            len(incoherent),
            0,
            "The coherence rule now flags zero scenarios. Either the 438 known "
            "mis-topiced labs were genuinely fixed (lower the ceiling to lock it "
            "in) or the vocabulary got so permissive it matches everything.",
        )


class CheckerUniquenessRuleTests(SimpleTestCase):
    def _tree(self, layout):
        """Build a scenarios/<tech>/<slug>/check.sh tree under a temp dir."""
        import tempfile

        base = Path(tempfile.mkdtemp())
        for tech, checks in layout.items():
            for i, body in enumerate(checks):
                d = base / tech / f"lab-{i:03d}"
                d.mkdir(parents=True)
                (d / "check.sh").write_text(body, encoding="utf-8")
        self.addCleanup(__import__("shutil").rmtree, base, True)
        return base

    def test_identical_checkers_are_counted_as_one_group(self):
        root = self._tree({"aws": ["#!/bin/bash\nexit 1\n"] * 6})
        groups = _sgi.duplicate_checker_groups(root)
        self.assertEqual(groups["aws"][0], 6)

    def test_distinct_checkers_do_not_form_a_group(self):
        root = self._tree({"aws": [f"#!/bin/bash\ncheck_{i}\n" for i in range(6)]})
        self.assertEqual(_sgi.duplicate_checker_groups(root)["aws"][0], 1)

    def test_trailing_whitespace_is_not_a_new_checker(self):
        """Normalisation, so whitespace churn cannot silently split a dupe group."""
        root = self._tree({"aws": ["#!/bin/bash\nexit 1\n", "#!/bin/bash   \nexit 1\n\n"]})
        self.assertEqual(_sgi.duplicate_checker_groups(root)["aws"][0], 2)

    def test_group_over_the_default_ceiling_is_a_regression(self):
        groups = {"newtech": (40, "d")}
        regressions = _sgi.duplicate_checker_regressions(groups, baseline={})
        self.assertEqual(regressions, [("newtech", 40, _sgi._DUPE_GROUP_DEFAULT_MAX)])

    def test_group_within_a_recorded_baseline_is_tolerated(self):
        """aws's 420 are pre-existing debt: recorded, not re-litigated every PR."""
        self.assertEqual(
            _sgi.duplicate_checker_regressions({"aws": (420, "d")}, baseline={"aws": 420}),
            [],
        )

    def test_growing_past_a_recorded_baseline_fails(self):
        self.assertEqual(
            _sgi.duplicate_checker_regressions({"aws": (421, "d")}, baseline={"aws": 420}),
            [("aws", 421, 420)],
        )

    def test_shrinking_below_the_baseline_is_fine(self):
        self.assertEqual(
            _sgi.duplicate_checker_regressions({"aws": (12, "d")}, baseline={"aws": 420}),
            [],
        )


class CheckerUniquenessRatchetTests(SimpleTestCase):
    def test_no_technology_exceeds_its_recorded_baseline(self):
        groups = _sgi.duplicate_checker_groups()
        self.assertGreater(len(groups), 10, "scenario tree not found or empty")
        regressions = _sgi.duplicate_checker_regressions(groups)
        self.assertEqual(
            regressions,
            [],
            "A technology grew its largest identical-check.sh group. N scenarios "
            "behind one byte-identical checker means N-1 are not graded on their "
            "own subject: "
            + "; ".join(f"{t} {o}>{a}" for t, o, a in regressions),
        )

    def test_the_aws_duplication_is_still_recorded(self):
        """Guards the baseline against being quietly reset to whatever is current.

        If someone regenerates _DUPE_GROUP_BASELINE from a tree where aws was
        cosmetically de-duplicated, the gate goes green with grading unchanged.
        """
        self.assertGreaterEqual(_sgi._DUPE_GROUP_BASELINE.get("aws", 0), 100)
