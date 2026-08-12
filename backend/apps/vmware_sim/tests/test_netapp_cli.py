"""Tests for the ONTAP CLI surface and LUN capacity arithmetic in netapp_engine.

Two contracts are covered:

1. The CLI is a true alias for System Manager clicks — typing the fix clears the
   same `broken` flag, and unrecognized commands fail with a non-zero rc.
2. LUNs obey the capacity of their containing volume, so an over-provisioning
   request fails on write instead of silently succeeding.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import netapp_engine as ne


class NetAppBaseTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "", *, login: bool = True) -> str:
        sid = f"test-ontap-{slug or 'plain'}"
        ne.drop_session(sid)
        ne.get_state(sid, slug)
        if login:
            ne.apply_action(sid, "login", {"user": "admin"})
        return sid


class CliContractTests(NetAppBaseTest):
    def test_unknown_object_is_a_nonzero_error(self):
        sid = self._session()
        res = ne.run_command(sid, "frobnicate show")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_unknown_verb_is_a_nonzero_error(self):
        sid = self._session()
        res = ne.run_command(sid, "volume frobnicate -volume vol_web_data")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_requires_login(self):
        sid = self._session(login=False)
        res = ne.run_command(sid, "volume show")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_ontap_size_literals(self):
        self.assertEqual(ne._ontap_size_gb("200GB"), 200)
        self.assertEqual(ne._ontap_size_gb("1TB"), 1024)
        self.assertEqual(ne._ontap_size_gb("500g"), 500)
        self.assertEqual(ne._ontap_size_gb("200"), 200)
        self.assertIsNone(ne._ontap_size_gb("banana"))

    def test_single_dash_options_parse(self):
        positionals, opts = ne._ontap_parse(
            ["volume", "create", "-volume", "vol_a", "-size", "100GB", "-aggregate", "aggr1"])
        self.assertEqual(positionals, ["volume", "create"])
        self.assertEqual(opts["size"], "100GB")
        self.assertEqual(opts["aggregate"], "aggr1")


class CliReadTests(NetAppBaseTest):
    def test_volume_show_reflects_state(self):
        sid = self._session()
        out = ne.run_command(sid, "volume show")["stdout"]
        self.assertIn("vol_web_data", out)
        self.assertIn("vol_db_data", out)
        self.assertIn("svm-prod", out)

    def test_snapmirror_show_reflects_state(self):
        sid = self._session()
        out = ne.run_command(sid, "snapmirror show")["stdout"]
        self.assertIn("svm-prod:vol_web_data", out)
        self.assertIn("snapmirrored", out)

    def test_other_show_commands(self):
        sid = self._session()
        self.assertIn("lun0", ne.run_command(sid, "lun show")["stdout"])
        self.assertIn("aggr1", ne.run_command(sid, "aggr show")["stdout"])
        self.assertIn("aggr1", ne.run_command(sid, "storage aggregate show")["stdout"])
        self.assertIn("svm-dr", ne.run_command(sid, "vserver show")["stdout"])
        self.assertIn("qt_users", ne.run_command(sid, "qtree show")["stdout"])
        self.assertIn("10.0.10.50", ne.run_command(sid, "network interface show")["stdout"])

    def test_volume_show_reflects_a_cli_resize(self):
        sid = self._session()
        ne.run_command(sid, "volume size -volume vol_web_data -new-size 300GB")
        self.assertIn("300GB", ne.run_command(sid, "volume show -volume vol_web_data")["stdout"])


class CliGradedOutcomeTests(NetAppBaseTest):
    def test_volume_resize_via_cli_clears_near_full_flag(self):
        sid = self._session("netapp-volume-resize-grow")
        self.assertFalse(ne.validate_netapp_lab(sid)[0])

        res = ne.run_command(sid, "volume size -volume vol_web_data -new-size 200GB")
        self.assertTrue(res["ok"], res)

        ok, reason = ne.validate_netapp_lab(sid)
        self.assertTrue(ok, reason)

    def test_lun_map_via_cli_clears_unmapped_flag(self):
        sid = self._session("netapp-lun-iscsi")
        self.assertFalse(ne.validate_netapp_lab(sid)[0])

        res = ne.run_command(
            sid, "lun map -path /vol/vol_db_data/lun0 -igroup iqn.1994-05.com.redhat:client1")
        self.assertTrue(res["ok"], res)

        ok, reason = ne.validate_netapp_lab(sid)
        self.assertTrue(ok, reason)

    def test_snapmirror_break_via_cli_clears_flag(self):
        sid = self._session("netapp-snapmirror-break")
        self.assertFalse(ne.validate_netapp_lab(sid)[0])

        res = ne.run_command(sid, "snapmirror break -destination-path svm-dr:vol_dr_copy")
        self.assertTrue(res["ok"], res)

        ok, reason = ne.validate_netapp_lab(sid)
        self.assertTrue(ok, reason)

    def test_snapmirror_create_via_cli_clears_flag(self):
        sid = self._session("netapp-snapmirror-create")
        res = ne.run_command(
            sid,
            "snapmirror create -source-path svm-prod:vol_db_data "
            "-destination-path svm-dr:vol_dr_copy2",
        )
        self.assertTrue(res["ok"], res)
        self.assertTrue(ne.validate_netapp_lab(sid)[0])

    def test_volume_create_via_cli_clears_flag(self):
        sid = self._session("netapp-volume-create")
        res = ne.run_command(sid, "volume create -volume vol_app -aggregate aggr1 -size 50GB")
        self.assertTrue(res["ok"], res)
        self.assertTrue(ne.validate_netapp_lab(sid)[0])

    def test_export_rule_create_via_cli_clears_flag(self):
        sid = self._session("netapp-export-nfs")
        res = ne.run_command(
            sid,
            "export-policy rule create -volume vol_db_data -policyname default "
            "-clientmatch 10.0.0.0/24 -rwrule sys",
        )
        self.assertTrue(res["ok"], res)
        self.assertTrue(ne.validate_netapp_lab(sid)[0])

    def test_volume_create_via_cli_respects_aggregate_capacity(self):
        sid = self._session()
        # aggr1 ships 1800/5000GB used, so a 9000GB request must be refused.
        res = ne.run_command(sid, "volume create -volume vol_huge -aggregate aggr1 -size 9000GB")
        self.assertFalse(res["ok"])
        self.assertIn("free", res["error"])


class LunCapacityTests(NetAppBaseTest):
    """LUNs are space-reserved against their containing volume."""

    def test_lun_cannot_exceed_containing_volume(self):
        sid = self._session()
        # vol_db_data is 200GB and already holds a 150GB LUN -> only 50GB left.
        res = ne.apply_action(sid, "create_lun", {"volume": "vol_db_data", "size_gb": 100})
        self.assertFalse(res["ok"])
        self.assertIn("50GB", res["error"])

    def test_lun_that_fits_is_accepted(self):
        sid = self._session()
        res = ne.apply_action(sid, "create_lun", {"volume": "vol_db_data", "size_gb": 50})
        self.assertTrue(res["ok"], res)

    def test_growing_the_volume_makes_the_lun_fit(self):
        """The documented remedy has to actually work, or the lab is a dead end."""
        sid = self._session()
        self.assertFalse(ne.apply_action(sid, "create_lun", {"volume": "vol_db_data", "size_gb": 100})["ok"])

        grow = ne.apply_action(sid, "resize_volume", {"name": "vol_db_data", "size_gb": 400})
        self.assertTrue(grow["ok"], grow)

        retry = ne.apply_action(sid, "create_lun", {"volume": "vol_db_data", "size_gb": 100})
        self.assertTrue(retry["ok"], retry)

    def test_lun_on_unknown_volume_is_rejected(self):
        sid = self._session()
        res = ne.apply_action(sid, "create_lun", {"volume": "vol_nope", "size_gb": 10})
        self.assertFalse(res["ok"])

    def test_zero_size_lun_rejected(self):
        sid = self._session()
        self.assertFalse(ne.apply_action(sid, "create_lun", {"volume": "vol_db_data", "size_gb": 0})["ok"])

    def test_seeded_lun_is_attributed_to_its_volume_by_path(self):
        sid = self._session()
        state = ne.get_state(sid)["state"]
        lun = state["luns"][0]
        self.assertEqual(ne._lun_volume(lun), "vol_db_data")
        vol = ne._find_volume(state, "vol_db_data")
        self.assertEqual(ne._volume_free_for_luns_gb(state, vol), 50)

    def test_lun_create_via_cli_enforces_the_same_capacity(self):
        sid = self._session()
        res = ne.run_command(sid, "lun create -path /vol/vol_db_data/lun9 -size 100GB")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)


class SeededScenariosRemainSolvableTests(NetAppBaseTest):
    """Capacity enforcement must not strand any shipped NetApp objective."""

    CASES = {
        "netapp-volume-resize-grow": ("resize_volume", {"name": "vol_web_data", "size_gb": 200}),
        "netapp-lun-iscsi": ("mount_lun", {"path": "/vol/vol_db_data/lun0"}),
        "netapp-snapmirror-create": ("create_snapmirror", {"source": "svm-prod:vol_db_data"}),
        "netapp-snapmirror-break": ("break_mirror", {"id": "sm1"}),
        "netapp-export-nfs": ("create_export", {"volume": "vol_db_data"}),
        "netapp-volume-create": ("create_volume", {"name": "vol_app", "aggregate": "aggr1", "size_gb": 50}),
    }

    def test_every_preset_fails_before_and_passes_after_its_documented_fix(self):
        for slug, (action, payload) in self.CASES.items():
            with self.subTest(slug=slug):
                cache.clear()
                sid = self._session(slug)
                self.assertFalse(ne.validate_netapp_lab(sid, slug)[0], f"{slug} passed before the fix")

                res = ne.apply_action(sid, action, payload)
                self.assertTrue(res["ok"], f"{slug}: {res}")

                ok, reason = ne.validate_netapp_lab(sid, slug)
                self.assertTrue(ok, f"{slug} still failing after its fix: {reason}")
