"""Windows simulator AD user actions."""

from django.test import SimpleTestCase, override_settings

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "fixitlab-windows-test",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class WindowsCreateAdUserTest(SimpleTestCase):
    def test_create_ad_user_with_groups(self):
        from apps.vmware_sim.windows_engine import apply_action, drop_session, get_state

        session_id = "test-win-create-user"
        get_state(session_id, "win-ad-unlock")
        result = apply_action(session_id, "create_ad_user", {
            "name": "jsmith",
            "display": "John Smith",
            "ou": "Users",
            "groups": ["Remote Desktop Users"],
            "must_change_pw": True,
        })
        self.assertTrue(result["ok"], result)

        state = get_state(session_id, "win-ad-unlock")
        users = state["ad"]["users"]
        user = next(u for u in users if u["name"] == "jsmith")
        self.assertIn("Remote Desktop Users", user["groups"])
        self.assertIn("Domain Users", user["groups"])
        self.assertTrue(user["must_change_pw"])
        self.assertEqual(user["ou"], "Users")

        drop_session(session_id)
