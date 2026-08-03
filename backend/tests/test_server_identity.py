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

    def test_sync_commvault_netapp_dellemc_soc(self):
        sid = "sess-storage-sync"
        self.addCleanup(si.drop_session, sid)

        si.sync_commvault_clients(sid, [
            {"name": "web01", "ip": "10.0.0.11", "status": "online", "backup_health": "protected"},
            {"name": "app01", "ip": "10.0.0.13", "status": "offline", "backup_health": "unprotected"},
        ])
        hosts = {s["hostname"]: s for s in si.list_servers(sid)}
        self.assertEqual(hosts["web01"]["power"], "on")
        self.assertEqual(hosts["app01"]["power"], "off")
        self.assertEqual(hosts["web01"]["tags"]["backup_health"], "protected")

        si.sync_netapp_storage(sid, {
            "summary": {"cluster": "fixitlab-cluster"},
            "clusters": [{"name": "fixitlab-cluster", "health": "ok"}],
            "volumes": [{"name": "vol_web_data", "size_gb": 100, "used_gb": 95}],
        })
        netapp = next(s for s in si.list_servers(sid) if s["tags"].get("persona") == "netapp")
        self.assertEqual(netapp["power"], "on")
        self.assertIn("vol_web_data", netapp["tags"]["volumes_near_full"])

        si.sync_dellemc_storage(sid, {
            "arrays": [{"id": "000297900123", "health": "normal"}],
            "volumes": [{"id": "0004", "storage_group": None}],
            "masking_views": [{"name": "MV_web01"}],
        })
        dell = next(s for s in si.list_servers(sid) if s["tags"].get("persona") == "dellemc")
        self.assertEqual(dell["power"], "on")
        self.assertIn("0004", dell["tags"]["volumes_unmapped"])

        si.sync_soc_assets(sid, [
            {"name": "ws-finance-07", "ip": "10.0.5.42", "risk": "critical", "quarantined": True},
            {"name": "web01", "ip": "10.0.0.11", "risk": "medium", "quarantined": False},
        ])
        soc_hosts = {s["hostname"]: s for s in si.list_servers(sid) if s["tags"].get("persona") == "soc"}
        self.assertEqual(soc_hosts["ws-finance-07"]["power"], "off")
        self.assertTrue(soc_hosts["ws-finance-07"]["tags"]["quarantined"])
        self.assertEqual(soc_hosts["web01"]["power"], "on")

    def test_sync_k8s_nodes(self):
        sid = "sess-k8s-sync"
        self.addCleanup(si.drop_session, sid)
        si.sync_k8s_nodes(sid, [
            {"name": "node1", "status": "Ready", "roles": ["control-plane"],
             "cpu_capacity": "8", "mem_capacity": "16Gi"},
            {"name": "node3", "status": "NotReady", "roles": ["worker"],
             "cpu_capacity": "4", "mem_capacity": "8Gi"},
        ])
        hosts = {s["hostname"]: s for s in si.list_servers(sid)}
        self.assertEqual(hosts["node1"]["power"], "on")
        self.assertEqual(hosts["node1"]["cpu"], 8)
        self.assertEqual(hosts["node1"]["mem_mb"], 16384)
        self.assertEqual(hosts["node3"]["power"], "off")
        self.assertEqual(hosts["node1"]["tags"]["role"], "control-plane")


class TerminalSshHostRegistrationTests(SimpleTestCase):
    """Cloud VMs synced into ServerIdentity must be reachable via lab SSH."""

    def setUp(self):
        from apps.labs.provisioner.simulation.shell import drop_sim_session, register_sim_session
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine

        self.sid = "si-ssh-host-session"
        si.drop_session(self.sid)
        drop_sim_session(self.sid)
        self.addCleanup(si.drop_session, self.sid)
        self.addCleanup(drop_sim_session, self.sid)
        cache.clear()
        self.engine = UnifiedSimulationEngine(scenario_slug="azure-resize", simulation_type="azure")
        self.engine.shell.state.session_id = self.sid
        register_sim_session(
            self.sid,
            f"sim-{self.sid}",
            "azure",
            {
                "engine": self.engine,
                "scenario_slug": "azure-resize",
                "hosts": {"primary": {"name": "primary", "ip": "10.10.1.4", "ssh_user": "root"}},
                "host_ips": {"10.10.1.4": "primary"},
            },
        )
        self.engine.shell._host_names = {"primary": {"name": "primary", "ip": "10.10.1.4"}}
        self.engine.shell._host_ips = {"10.10.1.4": "primary"}
        self.engine.shell._engine = self.engine

    def test_sync_azure_vm_registers_ssh_peer(self):
        si.sync_azure_vm(
            self.sid,
            {
                "name": "tf-web",
                "private_ip": "10.10.1.88",
                "size": "Standard_B2s",
                "power_state": "running",
                "lab_managed": True,
            },
            vm_sizes={"Standard_B2s": {"vcpus": 2, "ram_gb": 4}},
        )
        shell = self.engine.shell
        self.assertEqual(shell._host_ips.get("10.10.1.88"), "tf-web")
        self.assertIn("tf-web", shell._host_names)
        out = shell.run("ssh azureuser@tf-web")
        self.assertIn("Permanently added", out)
        self.assertNotIn("Connection refused", out)

    def test_sync_gcp_instance_ssh_by_ip(self):
        si.sync_gcp_instance(
            self.sid,
            {
                "name": "gcp-batch",
                "internal_ip": "10.128.0.55",
                "machine_type": "e2-medium",
                "status": "RUNNING",
                "lab_managed": True,
            },
            machine_types={"e2-medium": {"vcpus": 2, "ram_gb": 4}},
        )
        out = self.engine.shell.run("ssh ubuntu@10.128.0.55")
        self.assertIn("Permanently added", out)
        self.assertNotIn("Connection refused", out)


class S1AssetRegistryTests(SimpleTestCase):
    """Unified asset registry: MAAS → CMDB → AWX (S1 #210–211)."""

    def setUp(self):
        self.sid = "s1-asset-session"
        si.drop_session(self.sid)
        self.addCleanup(si.drop_session, self.sid)
        cache.clear()

    def test_upsert_from_maas_and_list_assets(self):
        asset = si.upsert_from_maas_machine(
            self.sid,
            {
                "name": "gpu-node-04",
                "status": "Ready",
                "power": "on",
                "ip": "10.64.12.14",
                "arch": "amd64/generic",
            },
            source="maas",
        )
        self.assertIsNotNone(asset)
        self.assertEqual(asset["install_state"], "Ready")
        self.assertTrue(asset["serial"])
        self.assertTrue(asset["asset_tag"])
        self.assertEqual(asset["owner"], "ai-infra")
        self.assertEqual(len(asset.get("gpus") or []), 8)
        rows = si.list_assets(self.sid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hostname"], "gpu-node-04")
        self.assertEqual(rows[0]["rack"], "R12")
        self.assertEqual(rows[0]["gpu_count"], 8)

    def test_maas_terminal_commission_mirrors_identity(self):
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine

        engine = UnifiedSimulationEngine(
            scenario_slug="ai-infra-maas-commission-h100",
            simulation_type="baremetal",
        )
        engine.lab_session_id = self.sid
        engine.shell.state.session_id = self.sid
        engine.shell.run("maas admin machine commission gpu-node-04")
        servers = si.list_servers(self.sid)
        names = {s["hostname"] for s in servers}
        self.assertIn("gpu-node-04", names)
        node = next(s for s in servers if s["hostname"] == "gpu-node-04")
        self.assertEqual(node["install_state"], "Ready")
        self.assertIn("maas", node["sources"])

    def test_awx_merges_maas_identity_hosts(self):
        from apps.vmware_sim import awx_engine as ae

        ae.drop_session(self.sid)
        self.addCleanup(ae.drop_session, self.sid)
        si.upsert_from_maas_machine(
            self.sid,
            {"name": "gpu-node-99", "status": "Deployed", "power": "on", "ip": "10.64.12.99"},
            source="maas",
        )
        ae.get_state(self.sid, "ai-infra-awx-nvidia-driver-rollout")
        ae.apply_action(self.sid, "login", {})
        state = ae.get_state(self.sid, "ai-infra-awx-nvidia-driver-rollout")["inventory"]
        names = [h["name"] for h in state["hosts"] if h.get("inventory") == "maas-gpu-nodes"]
        self.assertIn("gpu-node-99", names)
