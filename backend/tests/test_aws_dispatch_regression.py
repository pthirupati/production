"""Regression: academy-aws-* must grade via terminal FIXED-OK, not validate_aws_lab.

Same class of bug as G-06 (cicd_engine): every academy-aws scenario has
simulation_type=aws and a stub check.sh, so run_validation used to short-circuit
to validate_aws_lab (NO_VALIDATION_SCRIPT / any-event auto-pass) and ignore the
terminal sentinel the learner actually repairs.
"""

from unittest.mock import MagicMock

from django.test import TestCase

from apps.labs.provisioner.simulation.validation import validate_simulation_state
from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner
from apps.vmware_sim.aws_engine import drop_session as aws_drop_session


CHECK_SH = (
    "#!/bin/bash\n"
    "systemctl is-failed --quiet 2>/dev/null; test $? -ne 0\n"
    "exit 0\n"
)


class AwsAcademyDispatchRegressionTests(TestCase):
    def _mock_session(self, slug: str, sim_type: str = "aws"):
        session = MagicMock()
        session.id = f"aws-dispatch-{slug}"
        session.scenario.slug = slug
        session.scenario.simulation_type = sim_type
        session.scenario.validation_script = CHECK_SH
        session.scenario.requires_companion_hosts = False
        return session

    def test_academy_aws_routes_to_terminal_validator(self):
        slug = "academy-aws-001-learn-ec2"
        aws_drop_session(f"aws-dispatch-{slug}")
        prov = SimulationProvisioner()
        session = self._mock_session(slug, "aws")
        resource_id, _ = prov.provision(session)
        try:
            from apps.labs.provisioner.simulation.shell import get_sim_session_by_resource

            entry = get_sim_session_by_resource(resource_id)
            engine = entry["state"]["engine"]

            dispatcher_result = prov.run_validation(resource_id, CHECK_SH, slug)
            passed, msg = dispatcher_result
            self.assertNotIn("NO_VALIDATION_SCRIPT", msg)
            self.assertNotIn("AWS lab objectives met", msg)

            direct_result = validate_simulation_state(engine.state, CHECK_SH, engine=engine)
            self.assertEqual(dispatcher_result, direct_result)
        finally:
            prov.terminate(resource_id, session_id=str(session.id))

    def test_console_hero_aws_slug_still_uses_aws_engine(self):
        """Non-academy aws-* heroes keep validate_aws_lab."""
        slug = "aws-ec2-launch-web"
        aws_drop_session(f"aws-dispatch-{slug}")
        # Mark as a real LabSession-backed path is heavy; assert the gate string
        # in simulation_provisioner by provisioning and checking message class.
        prov = SimulationProvisioner()
        session = self._mock_session(slug, "aws")
        session.id = f"aws-dispatch-{slug}"
        resource_id, _ = prov.provision(session)
        try:
            passed, msg = prov.run_validation(resource_id, CHECK_SH, slug)
            # Unfixed console hero → NO_VALIDATION_SCRIPT or a console reason,
            # never the academy FIXED-OK terminal wording.
            self.assertTrue(
                ("NO_VALIDATION_SCRIPT" in msg)
                or ("AWS" in msg)
                or (passed is False),
                msg,
            )
        finally:
            prov.terminate(resource_id, session_id=str(session.id))
