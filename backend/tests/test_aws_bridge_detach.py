"""AWS console EBS detach: engine action, bridge reveal-removal, ServerIdentity sync.

Mirrors the attach-side coverage — a detach in the AWS console should free the
volume in aws_engine, queue a removal event the Linux terminal drains on its
next disk inspection, and clear the disk from the session's LabServer record.
"""

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import aws_bridge, server_identity as si
from apps.vmware_sim import aws_engine


class AwsDetachVolumeEngineTests(SimpleTestCase):
    def setUp(self):
        self.sid = "aws-detach-test"
        aws_engine.drop_session(self.sid)
        self.addCleanup(aws_engine.drop_session, self.sid)
        cache.clear()

    def test_detach_frees_volume_and_clears_device(self):
        aws_engine.get_state(self.sid)
        attach = aws_engine.apply_action(self.sid, "attach_volume", {
            "volume_id": "vol-test1", "instance_id": "i-test1", "size_gb": 30,
        })
        self.assertTrue(attach["ok"])
        device = attach["device"]

        detach = aws_engine.apply_action(self.sid, "detach_volume", {"volume_id": "vol-test1"})
        self.assertTrue(detach["ok"])
        self.assertEqual(detach["device"], device)

        state = aws_engine.get_state(self.sid)["state"]
        vol = next(v for v in state["volumes"] if v["id"] == "vol-test1")
        self.assertEqual(vol["state"], "available")
        self.assertIsNone(vol["attachedTo"])
        self.assertIsNone(vol["device"])

    def test_detach_missing_volume_fails_closed(self):
        aws_engine.get_state(self.sid)
        result = aws_engine.apply_action(self.sid, "detach_volume", {"volume_id": "vol-nope"})
        self.assertFalse(result["ok"])

    def test_detach_blocks_root_volume_while_running(self):
        aws_engine.get_state(self.sid)
        state = aws_engine.get_state(self.sid)["state"]
        inst = state["instances"][0]
        root_id = inst["rootVolume"]
        result = aws_engine.apply_action(self.sid, "detach_volume", {"volume_id": root_id})
        self.assertFalse(result["ok"])
        self.assertIn("root device", result["error"])


class AwsBridgeDetachTests(SimpleTestCase):
    def setUp(self):
        self.sid = "aws-bridge-detach-test"
        aws_bridge.clear(self.sid)
        si.drop_session(self.sid)
        self.addCleanup(aws_bridge.clear, self.sid)
        self.addCleanup(si.drop_session, self.sid)
        cache.clear()

    def test_attach_then_detach_round_trip(self):
        si.upsert_server(self.sid, {"hostname": "ip-10-1-1-5", "tags": {"role": "primary"}}, source="aws")
        primary = si.get_primary(self.sid)

        dev = aws_bridge.record_volume_attach(self.sid, "vol-a", size_gb=20, instance_id="i-1")
        # Not yet revealed to the terminal — consume to simulate `lsblk`.
        revealed = aws_bridge.consume_volume_events(self.sid)
        self.assertEqual(len(revealed), 1)
        self.assertEqual(revealed[0]["device"], dev)
        after_attach = si.get_server(self.sid, primary["id"])
        self.assertTrue(any(d["name"] == dev.split("/")[-1] for d in after_attach["disks"]))

        aws_bridge.record_volume_detach(self.sid, dev, instance_id="i-1")
        removed = aws_bridge.consume_removed_volume_events(self.sid)
        self.assertEqual(removed, [dev])
        after_detach = si.get_server(self.sid, primary["id"])
        self.assertFalse(any(d["name"] == dev.split("/")[-1] for d in after_detach["disks"]))

    def test_detach_never_revealed_is_dropped_not_queued(self):
        dev = aws_bridge.record_volume_attach(self.sid, "vol-b", size_gb=10, instance_id="i-2")
        # Detach before the terminal ever inspected disks — no removal event
        # should be queued since the guest never saw the device in the first place.
        aws_bridge.record_volume_detach(self.sid, dev, instance_id="i-2")
        self.assertEqual(aws_bridge.consume_volume_events(self.sid), [])
        self.assertEqual(aws_bridge.consume_removed_volume_events(self.sid), [])
