"""OpenStack Horizon engine foundation tests."""

from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import openstack_engine as eng


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class OpenStackEngineTests(SimpleTestCase):
    def setUp(self):
        self.sid = "os-test-session-1"
        eng.drop_session(self.sid)

    def tearDown(self):
        eng.drop_session(self.sid)

    def test_login_create_attach_resize(self):
        state = eng.get_state(self.sid, "openstack-attach-cinder-volume")
        self.assertFalse(state["state"]["session"]["logged_in"])

        r = eng.apply_action(self.sid, "login", {"user": "admin"})
        self.assertTrue(r["ok"])
        state = eng.get_state(self.sid)
        self.assertTrue(state["state"]["session"]["logged_in"])
        self.assertEqual(len(state["state"]["instances"]), 1)

        r = eng.apply_action(self.sid, "create_instance", {
            "name": "app-02", "flavor": "m1.small", "image": "ubuntu-22.04",
        })
        self.assertTrue(r["ok"])
        state = eng.get_state(self.sid)
        self.assertEqual(len(state["state"]["instances"]), 2)

        r = eng.apply_action(self.sid, "attach_volume", {
            "name": "vol-web-data", "instance": "web-01",
        })
        self.assertTrue(r["ok"])
        vol = next(v for v in state["state"]["volumes"] if v["name"] == "vol-web-data")
        # re-fetch after attach
        state = eng.get_state(self.sid)
        vol = next(v for v in state["state"]["volumes"] if v["name"] == "vol-web-data")
        self.assertEqual(vol["status"], "in-use")
        self.assertEqual(vol["device"], "/dev/vdb")

        r = eng.apply_action(self.sid, "resize_instance", {"name": "web-01", "flavor": "m1.large"})
        self.assertTrue(r["ok"])
        state = eng.get_state(self.sid)
        web = next(i for i in state["state"]["instances"] if i["name"] == "web-01")
        self.assertEqual(web["flavor"], "m1.large")

    def test_stop_start(self):
        eng.get_state(self.sid, "openstack-power")
        eng.apply_action(self.sid, "login", {"user": "admin"})
        r = eng.apply_action(self.sid, "stop_instance", {"name": "web-01"})
        self.assertTrue(r["ok"])
        state = eng.get_state(self.sid)
        web = state["state"]["instances"][0]
        self.assertEqual(web["status"], "SHUTOFF")
        r = eng.apply_action(self.sid, "start_instance", {"name": "web-01"})
        self.assertTrue(r["ok"])
        state = eng.get_state(self.sid)
        self.assertEqual(state["state"]["instances"][0]["status"], "ACTIVE")
