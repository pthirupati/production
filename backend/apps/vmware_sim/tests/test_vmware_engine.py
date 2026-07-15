"""Tests for the VMware vCenter/ESXi simulator hardware + network-sync engine.

Focus areas (the headline "guest ip a is desynced from NIC state" bug and the
new hardware-management actions):

  * set_nic_connected(false) pulls the primary link so the guest reports the NIC
    DOWN with no L3 address (NO-CARRIER, cable-unplugged semantics).
  * disconnect_network / connect_network are symmetric and drive nics[0].connected.
  * edit_disk grows capacity (grow-only) and adjusts datastore free space.
  * edit_nic operates on the *specified* NIC (not always nics[0]).
  * CD/DVD device add/remove + ISO mount/unmount.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import engine


class VmwareEngineBase(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "") -> str:
        sid = "test-vmware-hw"
        engine.drop_session(sid)
        engine.get_state(sid, slug)  # materialize + enrich inventory
        return sid

    def _vm(self, sid, vm_id="vm-api"):
        inv = engine.get_state(sid)["inventory"]
        return next(v for v in inv["vms"] if v["id"] == vm_id)


class NicConnectStateTests(VmwareEngineBase):
    def test_primary_nic_has_l2_l3_fields(self):
        sid = self._session()
        vm = self._vm(sid)
        nic0 = vm["nics"][0]
        self.assertIn("cable_connected", nic0)
        self.assertIn("ip_mode", nic0)
        self.assertTrue(nic0["connected"])
        self.assertTrue(nic0["cable_connected"])
        # guest_ip tracks the VM summary IP for the primary adapter.
        self.assertEqual(nic0["guest_ip"], vm["ip"])

    def test_set_nic_connected_false_marks_primary_link_down(self):
        """Headline bug: disconnecting the NIC must reflect down at the guest."""
        sid = self._session()
        vm = self._vm(sid)
        nic0_id = vm["nics"][0]["id"]

        res = engine.apply_action(sid, "set_nic_connected",
                                  {"vm_id": vm["id"], "nic_id": nic0_id, "connected": False})
        self.assertTrue(res["ok"], res)

        vm2 = self._vm(sid)
        nic0 = vm2["nics"][0]
        # The guest-facing state the terminal renders from must show the link down.
        self.assertFalse(nic0["connected"])
        self.assertFalse(nic0["cable_connected"])
        self.assertTrue(vm2.get("network_disconnected"))
        # primaryNicUp (JS) mirror: down when connected/cable false or vm disconnected.
        self.assertTrue(
            vm2.get("network_disconnected")
            or nic0["connected"] is False
            or nic0["cable_connected"] is False
        )

    def test_set_nic_connected_true_brings_primary_link_up(self):
        sid = self._session()
        vm = self._vm(sid)
        nic0_id = vm["nics"][0]["id"]
        engine.apply_action(sid, "set_nic_connected",
                            {"vm_id": vm["id"], "nic_id": nic0_id, "connected": False})
        res = engine.apply_action(sid, "set_nic_connected",
                                  {"vm_id": vm["id"], "nic_id": nic0_id, "connected": True})
        self.assertTrue(res["ok"], res)
        vm2 = self._vm(sid)
        self.assertTrue(vm2["nics"][0]["connected"])
        self.assertTrue(vm2["nics"][0]["cable_connected"])
        self.assertFalse(vm2.get("network_disconnected"))

    def test_disconnect_then_connect_network_is_symmetric(self):
        sid = self._session()
        vm = self._vm(sid)
        r1 = engine.apply_action(sid, "disconnect_network", {"vm_id": vm["id"]})
        self.assertTrue(r1["ok"], r1)
        vm_dc = self._vm(sid)
        self.assertTrue(vm_dc.get("network_disconnected"))
        self.assertFalse(vm_dc["nics"][0]["connected"])
        self.assertFalse(vm_dc["nics"][0]["cable_connected"])

        r2 = engine.apply_action(sid, "connect_network", {"vm_id": vm["id"]})
        self.assertTrue(r2["ok"], r2)
        vm_up = self._vm(sid)
        self.assertFalse(vm_up.get("network_disconnected"))
        self.assertTrue(vm_up["nics"][0]["connected"])
        self.assertTrue(vm_up["nics"][0]["cable_connected"])

    def test_set_nic_connected_unknown_nic_errors(self):
        sid = self._session()
        vm = self._vm(sid)
        res = engine.apply_action(sid, "set_nic_connected",
                                  {"vm_id": vm["id"], "nic_id": "no-such-nic", "connected": False})
        self.assertFalse(res["ok"])


class EditNicTests(VmwareEngineBase):
    def test_edit_nic_targets_specified_nic_not_just_first(self):
        sid = self._session()
        vm = self._vm(sid)
        # Add a second NIC so there is a non-primary target.
        engine.apply_action(sid, "add_nic", {"vm_id": vm["id"], "network_id": "net-03"})
        vm2 = self._vm(sid)
        self.assertGreaterEqual(len(vm2["nics"]), 2)
        second = vm2["nics"][1]
        res = engine.apply_action(sid, "edit_nic",
                                  {"vm_id": vm["id"], "nic_id": second["id"],
                                   "network_id": "net-04", "adapter_type": "E1000E"})
        self.assertTrue(res["ok"], res)
        vm3 = self._vm(sid)
        # The *second* NIC changed; the primary NIC's network is untouched.
        self.assertEqual(vm3["nics"][1]["network_id"], "net-04")
        self.assertEqual(vm3["nics"][1]["adapter_type"], "E1000E")
        self.assertEqual(vm3["nics"][0]["network_id"], vm2["nics"][0]["network_id"])


class EditDiskTests(VmwareEngineBase):
    def test_edit_disk_grows_capacity_and_reduces_ds_free(self):
        sid = self._session()
        vm = self._vm(sid)
        disk = vm["disks"][0]
        old_cap = disk["capacity_gb"]
        inv = engine.get_state(sid)["inventory"]
        ds = next(d for d in inv["datastores"] if d["id"] == disk["datastore_id"])
        old_free = ds["free_gb"]

        new_cap = old_cap + 20
        res = engine.apply_action(sid, "edit_disk",
                                  {"vm_id": vm["id"], "disk_id": disk["id"], "size_gb": new_cap})
        self.assertTrue(res["ok"], res)

        vm2 = self._vm(sid)
        d2 = next(d for d in vm2["disks"] if d["id"] == disk["id"])
        self.assertEqual(d2["capacity_gb"], new_cap)
        inv2 = engine.get_state(sid)["inventory"]
        ds2 = next(d for d in inv2["datastores"] if d["id"] == disk["datastore_id"])
        self.assertEqual(ds2["free_gb"], old_free - 20)

    def test_edit_disk_cannot_shrink(self):
        sid = self._session()
        vm = self._vm(sid)
        disk = vm["disks"][0]
        res = engine.apply_action(sid, "edit_disk",
                                  {"vm_id": vm["id"], "disk_id": disk["id"],
                                   "size_gb": max(1, disk["capacity_gb"] - 5)})
        self.assertFalse(res["ok"])
        self.assertIn("shrink", res["error"].lower())

    def test_edit_disk_powered_on_flags_pending_resize(self):
        sid = self._session()
        vm = self._vm(sid, "vm-db")  # vm-db is poweredOn in the base inventory
        self.assertEqual(vm["power"], "poweredOn")
        disk = vm["disks"][0]
        res = engine.apply_action(sid, "edit_disk",
                                  {"vm_id": vm["id"], "disk_id": disk["id"],
                                   "size_gb": disk["capacity_gb"] + 50})
        self.assertTrue(res["ok"], res)
        vm2 = self._vm(sid, "vm-db")
        self.assertTrue(vm2.get("guest_disk_resize_pending"))


class CdromTests(VmwareEngineBase):
    def test_vm_has_default_cdrom(self):
        sid = self._session()
        vm = self._vm(sid)
        self.assertTrue(vm.get("cdroms"))
        self.assertFalse(vm["cdroms"][0]["connected"])

    def test_add_mount_unmount_remove_cdrom(self):
        sid = self._session()
        vm = self._vm(sid)
        r_add = engine.apply_action(sid, "add_cdrom", {"vm_id": vm["id"]})
        self.assertTrue(r_add["ok"], r_add)
        vm2 = self._vm(sid)
        self.assertGreaterEqual(len(vm2["cdroms"]), 2)
        cd = vm2["cdroms"][-1]

        r_mount = engine.apply_action(sid, "mount_iso",
                                      {"vm_id": vm["id"], "cdrom_id": cd["id"],
                                       "iso_path": "[datastore-ssd-01] iso/rhel8.iso"})
        self.assertTrue(r_mount["ok"], r_mount)
        vm3 = self._vm(sid)
        cd3 = next(c for c in vm3["cdroms"] if c["id"] == cd["id"])
        self.assertTrue(cd3["connected"])
        self.assertEqual(cd3["iso_path"], "[datastore-ssd-01] iso/rhel8.iso")

        r_unmount = engine.apply_action(sid, "unmount_iso",
                                        {"vm_id": vm["id"], "cdrom_id": cd["id"]})
        self.assertTrue(r_unmount["ok"], r_unmount)
        vm4 = self._vm(sid)
        cd4 = next(c for c in vm4["cdroms"] if c["id"] == cd["id"])
        self.assertFalse(cd4["connected"])
        self.assertEqual(cd4["iso_path"], "")

        r_rm = engine.apply_action(sid, "remove_cdrom",
                                   {"vm_id": vm["id"], "cdrom_id": cd["id"]})
        self.assertTrue(r_rm["ok"], r_rm)
        vm5 = self._vm(sid)
        self.assertNotIn(cd["id"], [c["id"] for c in vm5["cdroms"]])
