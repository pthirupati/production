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

    def test_scenario_lab_servers_are_session_scoped(self):
        """Different sessions must not share LabServers (no platform-global host)."""
        a = si.seed_scenario_lab_servers("sess-a", sim_type="linux", slug="linux-sshd-down")
        b = si.seed_scenario_lab_servers("sess-b", sim_type="linux", slug="linux-sshd-down")
        self.addCleanup(si.drop_session, "sess-a")
        self.addCleanup(si.drop_session, "sess-b")
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(len(si.list_servers("sess-a")), 1)
        self.assertEqual(len(si.list_servers("sess-b")), 1)
        # Same hostname shape is fine; ids live in different session keys.
        self.assertEqual(si.get_primary("sess-a")["hostname"], a["hostname"])

    def test_windows_and_k8s_personas_seed(self):
        w = si.seed_scenario_lab_servers("sess-win", sim_type="windows", slug="win-sccm-patch-failed")
        k = si.seed_scenario_lab_servers("sess-k8s", sim_type="kubernetes", slug="k8s-pod-crashloop")
        self.addCleanup(si.drop_session, "sess-win")
        self.addCleanup(si.drop_session, "sess-k8s")
        self.assertEqual(w["os"], "windows-server-2022")
        self.assertEqual(k["tags"]["persona"], "kubernetes")
        bm = si.seed_scenario_lab_servers(
            "sess-bm", sim_type="baremetal", slug="maas-ipmi-bmc-unreachable",
        )
        self.addCleanup(si.drop_session, "sess-bm")
        self.assertEqual(bm["physical_location"]["rack"], "R12")

    def test_hero_yaml_lab_servers_seed_multiple(self):
        """Hero scenarios declare lab_servers; seed should materialize them."""
        sid = "sess-cv"
        primary = si.seed_scenario_lab_servers(
            sid, sim_type="commvault", slug="cv-vm-backup-missing-client",
        )
        self.addCleanup(si.drop_session, sid)
        self.assertIsNotNone(primary)
        hosts = {s["hostname"] for s in si.list_servers(sid)}
        self.assertIn("db01", hosts)
        self.assertIn("app-migrated-01", hosts)
        self.assertEqual(primary["hostname"], "db01")
        self.assertEqual(primary["tags"]["role"], "primary")

    def test_dc_yaml_physical_location(self):
        sid = "sess-dc"
        primary = si.seed_scenario_lab_servers(
            sid, sim_type="datacenter", slug="dc-failed-nic-reseat",
        )
        self.addCleanup(si.drop_session, sid)
        self.assertEqual(primary["hostname"], "db-prod-01")
        self.assertEqual(primary["physical_location"]["rack"], "R02")
        self.assertEqual(primary["physical_location"]["u_position"], 10)

    def test_sync_awx_and_monitoring_and_windows(self):
        sid = "sess-sync-multi"
        self.addCleanup(si.drop_session, sid)
        si.sync_awx_inventory(sid, [
            {"id": "h1", "name": "web01.fixitlab.local", "inventory": "Production",
             "enabled": True, "status": "ok", "ip": "10.1.1.10"},
            {"id": "h2", "name": "db01", "inventory": "Production",
             "enabled": False, "status": "ok", "ip": "10.1.1.20"},
        ])
        hosts = {s["hostname"]: s for s in si.list_servers(sid)}
        self.assertEqual(hosts["web01"]["power"], "on")
        self.assertEqual(hosts["db01"]["power"], "off")
        self.assertIn("awx", hosts["web01"]["sources"])

        si.sync_monitoring_targets(sid, [
            {"job": "node", "instance": "10.2.2.5:9100", "health": "up",
             "labels": {"host": "mon-web", "job": "node"}},
            {"job": "node", "instance": "10.2.2.6:9100", "health": "down",
             "labels": {"host": "mon-db", "job": "node"}},
        ])
        hosts = {s["hostname"]: s for s in si.list_servers(sid)}
        self.assertEqual(hosts["mon-web"]["power"], "on")
        self.assertEqual(hosts["mon-db"]["power"], "off")

        w = si.sync_windows_host(sid, {
            "computer_name": "WIN-APP01",
            "os": "windows-server-2022",
            "domain": {"name": "CORP", "joined": True},
            "session": {"logged_in": True, "locked": False},
            "network": {"adapters": [{"name": "Ethernet0", "ip": "10.20.60.55", "connected": True}]},
        })
        self.assertEqual(w["hostname"], "WIN-APP01")
        self.assertEqual(w["primary_ip"], "10.20.60.55")
        self.assertEqual(w["power"], "on")
