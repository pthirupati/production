"""ServerIdentity foundation tests."""

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import server_identity as si


class ServerIdentityTests(SimpleTestCase):
    def setUp(self):
        self.sid = "si-test-session"
        si.drop_session(self.sid)
        self.addCleanup(si.drop_session, self.sid)
        cache.clear()

    def test_upsert_and_list(self):
        s = si.upsert_server(self.sid, {"hostname": "web-prod-01", "primary_ip": "10.1.1.10", "cpu": 4}, source="test")
        self.assertEqual(s["hostname"], "web-prod-01")
        self.assertIn("test", s["sources"])
        listed = si.list_servers(self.sid)
        self.assertEqual(len(listed), 1)
        self.assertEqual(si.get_primary(self.sid)["hostname"], "web-prod-01")

    def test_attach_disk_and_events(self):
        s = si.upsert_server(self.sid, {"hostname": "db01", "tags": {"role": "primary"}}, source="vmware")
        si.attach_disk(self.sid, s["id"], name="sdb", size_gb=50, source="vmware")
        again = si.get_server(self.sid, s["id"])
        self.assertTrue(any(d["name"] == "sdb" for d in again["disks"]))
        events = si.consume_events(self.sid)
        types = {e["type"] for e in events}
        self.assertIn("server.disk_attached", types)
        self.assertIn("server.upserted", types)

    def test_seed_from_aws_and_power(self):
        s = si.seed_from_aws_instance(
            self.sid,
            {"id": "i-abc", "name": "web", "privateIp": "172.31.14.52", "state": "running", "os": "amazon-linux-2023"},
        )
        self.assertEqual(s["hostname"], "ip-172-31-14-52")
        si.set_power(self.sid, s["id"], "off", source="aws")
        self.assertEqual(si.get_server(self.sid, s["id"])["power"], "off")
