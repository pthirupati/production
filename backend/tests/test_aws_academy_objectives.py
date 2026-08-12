"""academy-aws-* console objectives: mapped, broken on arrival, and solvable.

The 420 academy-aws packs used to seed an empty `broken` dict (the substring
heuristics in _apply_preset only ever matched *-security-groups-*), so the
provisioner excluded the whole family from validate_aws_lab. Now that
_apply_academy_preset authors per-slug markers, the contract those markers must
hold is:

  1. every academy slug either seeds a marker or names a service on the
     deliberate read-only allowlist — no silent gaps;
  2. a mapped lab grades FAIL on a freshly seeded world (no auto-pass);
  3. the documented console fix actually clears it (no unsolvable lab);
  4. an unmapped lab reports NO_VALIDATION_SCRIPT so the dispatcher falls
     through to the terminal sentinel instead of stranding the learner.
"""

import os

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import aws_engine as ae
from apps.vmware_sim.aws_v2_facades import ensure_v2

SCENARIO_DIR = "/Users/tponguluri/fixitlab/scenarios/aws"


def _academy_slugs() -> list[str]:
    if not os.path.isdir(SCENARIO_DIR):
        return []
    return sorted(s for s in os.listdir(SCENARIO_DIR) if s.startswith("academy-aws-"))


def _documented_fix(broken: dict, state: dict) -> list[tuple[str, dict]]:
    """The console actions a learner performs to clear each marker kind."""
    if "require_launch" in broken:
        r = broken["require_launch"]
        return [("launch_instance", {"type": r["type"], "name": r["name"], "count": 1})]
    if "require_running" in broken:
        return [("start_instance", {"id": broken["require_running"]})]
    if "require_stopped" in broken:
        return [("stop_instance", {"id": broken["require_stopped"]})]
    if "require_tag" in broken:
        r = broken["require_tag"]
        return [("set_tags", {"id": r["name"], "tags": {r["key"]: r["value"]}})]
    if "restrict_ssh_sg" in broken:
        sg = ae._sg_by_name(state, broken["restrict_ssh_sg"])
        rid = next(r["id"] for r in sg["inbound"]
                   if r["from"] <= 22 <= r["to"] and r["source"] == "0.0.0.0/0")
        return [("remove_sg_rule", {"group_name": broken["restrict_ssh_sg"], "rule_id": rid})]
    if "require_bucket_encrypted" in broken:
        return [("update_bucket", {"name": broken["require_bucket_encrypted"],
                                   "patch": {"encryption": "SSE-S3"}})]
    if "require_bucket_private" in broken:
        return [("update_bucket", {"name": broken["require_bucket_private"],
                                   "patch": {"publicAccess": "Bucket and objects not public"}})]
    if "require_instance_in_subnet" in broken:
        return [("launch_instance", {"type": "t3.micro", "name": "private-app",
                                     "subnetId": broken["require_instance_in_subnet"], "count": 1})]
    if "require_cw_alarm" in broken:
        return [("create_cw_alarm", {"name": broken["require_cw_alarm"],
                                     "metric": "CPUUtilization", "namespace": "AWS/EC2"})]
    if "require_lambda" in broken:
        return [("create_lambda", {"name": broken["require_lambda"]})]
    if "require_rds" in broken:
        return [("create_rds", {"name": broken["require_rds"]})]
    if "require_dynamodb_table" in broken:
        return [("create_dynamodb_table", {"name": broken["require_dynamodb_table"]})]
    if "require_asg_desired" in broken:
        r = broken["require_asg_desired"]
        return [("scale_asg", {"name": r["name"], "desired": r["min"], "max": max(r["min"], 4)})]
    if "require_route53_record" in broken:
        r = broken["require_route53_record"]
        return [("create_hosted_zone", {"name": "lab.internal"}),
                ("upsert_route53_record", {"zone": "lab.internal", "record_name": r["name"],
                                           "type": r["type"], "value": "10.0.0.10"})]
    if "require_instance_role" in broken:
        r = broken["require_instance_role"]
        return [("attach_instance_role", {"instance_id": r["name"], "role": r["role"]})]
    raise AssertionError(f"no documented fix registered for marker {sorted(broken)}")


class AcademyAwsSlugParsingTests(SimpleTestCase):
    def test_parses_category_and_service(self):
        self.assertEqual(ae._academy_parts("academy-aws-001-learn-ec2"), ("learn", "ec2"))
        self.assertEqual(
            ae._academy_parts("academy-aws-135-production-security-groups-14"),
            ("production", "security-groups"),
        )
        self.assertEqual(
            ae._academy_parts("academy-aws-242-build-sts-assume-role-5"),
            ("build", "sts-assume-role"),
        )

    def test_non_academy_slug_is_not_parsed(self):
        self.assertIsNone(ae._academy_parts("aws-ec2-launch-web"))
        self.assertIsNone(ae._academy_parts("terraform-state-lock"))

    def test_academy_slug_bypasses_greedy_substring_heuristics(self):
        """'sg'/'tag' substrings must not steal an academy slug's objective."""
        state = ae._base_state()
        ae._apply_preset(state, "academy-aws-083-operate-iam-9")
        # 'operate-iam-9' contains no sg/tag substring, but the point is that the
        # academy branch owns the mapping: IAM packs get the role objective.
        self.assertEqual(sorted(state["broken"]), ["require_instance_role"])


class AcademyAwsCoverageTests(SimpleTestCase):
    def test_every_academy_slug_is_mapped_or_deliberately_allowlisted(self):
        slugs = _academy_slugs()
        self.assertTrue(slugs, "academy-aws scenarios not found on disk")
        gaps = []
        for slug in slugs:
            state = ae._base_state()
            ae._apply_preset(state, slug)
            if state.get("broken"):
                continue
            category, service = ae._academy_parts(slug)
            if service not in ae._ACADEMY_UNMAPPED_OK:
                gaps.append((slug, service))
        self.assertEqual(gaps, [], f"academy slugs with neither a marker nor an allowlist entry: {gaps}")

    def test_a_meaningful_share_of_packs_get_console_objectives(self):
        """Guards against the mapping silently regressing to near-zero coverage."""
        slugs = _academy_slugs()
        mapped = 0
        for slug in slugs:
            state = ae._base_state()
            ae._apply_preset(state, slug)
            if state.get("broken"):
                mapped += 1
        self.assertGreaterEqual(mapped, 200, f"only {mapped}/{len(slugs)} academy packs mapped")


class AcademyAwsSolvabilityTests(SimpleTestCase):
    """Unfixed -> FAIL, documented fix -> PASS, for every mapped academy pack."""

    def setUp(self):
        cache.clear()

    def _seed(self, slug: str) -> str:
        sid = f"academy-solve-{slug}"
        ae.clear_session(sid)
        self.addCleanup(ae.clear_session, sid)
        entry = ae._ensure(sid, slug)
        ensure_v2(entry["state"])
        ae._save(sid, entry)
        return sid

    def _settle_lifecycle(self, sid: str) -> None:
        """Land any pending start/stop transition instead of sleeping on it."""
        entry = ae._load(sid)
        for inst in entry["state"].get("instances", []):
            if inst.get("_transition"):
                inst["_transition"]["at"] = 0
        ae._save(sid, entry)

    def test_every_mapped_pack_starts_broken_and_is_solvable(self):
        unsolvable, auto_pass, action_errors = [], [], []
        for slug in _academy_slugs():
            sid = self._seed(slug)
            broken = dict(ae._load(sid)["state"].get("broken") or {})
            if not broken:
                continue

            ok, msg = ae.validate_aws_lab(sid, slug)
            if ok:
                auto_pass.append((slug, msg))
                continue

            state = ae._load(sid)["state"]
            for action, payload in _documented_fix(broken, state):
                result = ae.apply_action(sid, action, payload)
                if not result.get("ok"):
                    action_errors.append((slug, action, result.get("error")))
                    break
            self._settle_lifecycle(sid)

            ok, msg = ae.validate_aws_lab(sid, slug)
            if not ok:
                unsolvable.append((slug, sorted(broken), msg))

        self.assertEqual(auto_pass, [], f"packs graded PASS on a freshly seeded world: {auto_pass[:5]}")
        self.assertEqual(action_errors, [], f"documented fix action rejected: {action_errors[:5]}")
        self.assertEqual(unsolvable, [], f"packs still FAIL after the documented fix: {unsolvable[:5]}")

    def test_unmapped_pack_reports_no_validation_script(self):
        """So the dispatcher falls through to the terminal sentinel path."""
        slug = next(
            (s for s in _academy_slugs()
             if ae._academy_parts(s)[1] in ae._ACADEMY_UNMAPPED_OK),
            None,
        )
        self.assertIsNotNone(slug, "expected at least one allowlisted academy pack")
        sid = self._seed(slug)
        ok, msg = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok)
        self.assertEqual(msg, "NO_VALIDATION_SCRIPT")

    def test_unmapped_pack_does_not_auto_pass_on_console_activity(self):
        """A console click must not award a pass for an unmapped objective."""
        slug = next(
            s for s in _academy_slugs()
            if ae._academy_parts(s)[1] in ae._ACADEMY_UNMAPPED_OK
        )
        sid = self._seed(slug)
        ae.apply_action(sid, "set_region", {"region": "us-west-2"})
        ae.apply_action(sid, "create_bucket", {"name": "learner-made-a-bucket-000001"})
        ok, msg = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok, f"unmapped pack auto-passed after console activity: {msg}")


class AcademyAwsObjectiveShapeTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_vpc_pack_does_not_grade_the_prebuilt_private_subnet_instance(self):
        """require_instance_in_subnet would pre-pass: app-server-01 already lives there."""
        state = ae._base_state()
        ae._apply_preset(state, "academy-aws-004-troubleshoot-vpc")
        self.assertNotIn("require_instance_in_subnet", state["broken"])
        seeded = next(i for i in state["instances"] if i["name"] == "app-server-01")
        self.assertEqual(seeded["subnetId"], "subnet-0a1b2c3d4e5f10003")
        self.assertEqual(seeded["state"], "stopped")

    def test_cloudwatch_pack_removes_the_alarm_it_asks_for(self):
        state = ae._base_state()
        ae._apply_preset(state, "academy-aws-048-observability-cloudwatch-5")
        self.assertEqual(state["broken"]["require_cw_alarm"], "HighCPUUtilization")
        self.assertNotIn("HighCPUUtilization", [a["name"] for a in state["cwAlarms"]])

    def test_s3_security_pack_targets_the_public_bucket(self):
        state = ae._base_state()
        ae._apply_preset(state, "academy-aws-101-security-s3")
        self.assertEqual(state["broken"]["require_bucket_private"], "my-web-assets-demo-123456")
        bucket = next(b for b in state["s3Buckets"] if b["name"] == "my-web-assets-demo-123456")
        self.assertNotIn("not public", bucket["publicAccess"].lower())

    def test_every_mapped_pack_carries_a_learner_facing_goal(self):
        for slug in _academy_slugs():
            state = ae._base_state()
            ae._apply_preset(state, slug)
            if not state.get("broken"):
                continue
            goal = state.get("goal") or {}
            self.assertTrue(goal.get("title"), f"{slug} has no goal title")
            self.assertTrue(goal.get("objective"), f"{slug} has no goal objective")
