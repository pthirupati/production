"""Regression: devops/cicd/pipeline/gitlab-ci/github-actions scenarios must be
graded against real terminal state (check.sh via validate_simulation_state),
never against the orphaned cicd_engine job-DAG model that no frontend writes to.

Root cause (found during the P0 audit): `SimulationProvisioner.run_validation`
used to intercept ANY scenario whose simulation_type=="devops" OR whose slug
started with devops-/cicd-/pipeline-/gitlab-ci-/github-actions- and routed it
straight to `cicd_engine.validate_cicd_lab` — before check.sh ever ran. Every
scenario in that catalog is actually terminal-only (git repo + gitlab-runner
config + Helm state seeded via the separate in-memory DevOpsState object), so
those labs could never pass no matter what the learner did in the terminal.
This test locks in the fix: the dispatcher must fall through to
`validate_simulation_state` for these scenarios.
"""

from unittest.mock import MagicMock

from django.test import TestCase

from apps.labs.provisioner.simulation.validation import validate_simulation_state
from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner
from apps.vmware_sim.cicd_engine import drop_session as cicd_drop_session


CHECK_SH = (
    "#!/bin/bash\n"
    "if [ -f /tmp/pipeline-fixed ]; then\n"
    "  echo PASS\n"
    "  exit 0\n"
    "fi\n"
    "echo FAIL\n"
    "exit 1\n"
)


class CicdDispatchRegressionTests(TestCase):
    # run_validation's dispatch chain re-fetches LabSession from the DB when
    # the cached sim entry lacks a raw simulation_type — matches
    # ValidationTests/ProvisionerTests in test_simulation_os.py.
    def _mock_session(self, slug: str, sim_type: str):
        session = MagicMock()
        session.id = f"cicd-dispatch-{slug}"
        session.scenario.slug = slug
        session.scenario.simulation_type = sim_type
        session.scenario.validation_script = CHECK_SH
        session.scenario.requires_companion_hosts = False
        return session

    def _assert_routes_to_terminal_validator(self, slug: str, sim_type: str):
        """Prove `run_validation` is deciding via validate_simulation_state
        (the terminal check.sh grader), not cicd_engine.validate_cicd_lab.

        The strongest, most direct proof: the dispatcher's verdict must be
        byte-identical to calling validate_simulation_state directly on the
        same engine state/script — cicd_engine never enters the picture, and
        we don't depend on this particular check.sh's exact line syntax being
        one the terminal's canonical-check matcher happens to recognize.
        """
        cicd_drop_session(f"cicd-dispatch-{slug}")
        prov = SimulationProvisioner()
        session = self._mock_session(slug, sim_type)
        resource_id, _ = prov.provision(session)
        try:
            from apps.labs.provisioner.simulation.shell import get_sim_session_by_resource

            entry = get_sim_session_by_resource(resource_id)
            engine = entry["state"]["engine"]

            dispatcher_result = prov.run_validation(resource_id, CHECK_SH, slug)
            passed, msg = dispatcher_result
            # The bug: cicd_engine.validate_cicd_lab short-circuits with one of
            # these exact strings before check.sh ever runs. If routing is
            # fixed, neither ever appears.
            self.assertNotIn("CI/CD pipeline session", msg)
            self.assertNotIn("Unresolved pipeline fault", msg)

            direct_result = validate_simulation_state(engine.state, CHECK_SH, engine=engine)
            self.assertEqual(dispatcher_result, direct_result)
        finally:
            prov.terminate(resource_id, session_id=str(session.id))

    def test_devops_simulation_type_slug_not_intercepted(self):
        # Mirrors real hero-style scenarios: cicd-pipeline-broken,
        # gitlab-ci-runner-stuck (simulation_type: devops explicitly).
        self._assert_routes_to_terminal_validator("cicd-pipeline-broken", "devops")

    def test_generic_devops_prefixed_slug_not_intercepted(self):
        # Mirrors the academy catalog: devops-ci-pipeline-*, academy-devops-*
        # (simulation_type: generic; only the slug carries the devops- prefix).
        self._assert_routes_to_terminal_validator("devops-ci-pipeline-bad-image-tag", "generic")

    def test_pipeline_and_github_actions_prefixes_not_intercepted(self):
        self._assert_routes_to_terminal_validator("pipeline-broken-demo", "generic")
        self._assert_routes_to_terminal_validator("github-actions-secret-missing", "devops")

    def test_matches_direct_validate_simulation_state_call(self):
        """The dispatcher's answer must equal calling validate_simulation_state
        directly on the same engine state — the strongest proof it is the
        terminal validator (not cicd_engine) deciding the outcome."""
        cicd_drop_session("cicd-dispatch-direct-compare")
        prov = SimulationProvisioner()
        session = self._mock_session("devops-direct-compare", "devops")
        session.id = "cicd-dispatch-direct-compare"
        resource_id, _ = prov.provision(session)
        try:
            from apps.labs.provisioner.simulation.shell import get_sim_session_by_resource
            entry = get_sim_session_by_resource(resource_id)
            engine = entry["state"]["engine"]

            dispatcher_result = prov.run_validation(resource_id, CHECK_SH, "devops-direct-compare")
            direct_result = validate_simulation_state(engine.state, CHECK_SH, engine=engine)
            self.assertEqual(dispatcher_result, direct_result)
        finally:
            prov.terminate(resource_id, session_id="cicd-dispatch-direct-compare")
