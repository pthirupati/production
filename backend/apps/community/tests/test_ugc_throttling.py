"""UGC write-throttling tests.

The community app shipped with no throttling on any write path, so an
authenticated script could post threads/replies and upload 5 MB images in a loop.

Two things worth knowing about testing this:

1. ``config/test_settings`` monkey-patches ``SimpleRateThrottle.allow_request``
   to always return True, so an end-to-end 429 is unreachable in the suite by
   design (tests must not be rate-limited). These tests therefore assert the
   *decision logic* directly rather than a live 429.

2. ``test_settings`` also REPLACES ``DEFAULT_THROTTLE_RATES`` rather than
   extending it, so a new scope must be registered there too. Adding the ugc_*
   scopes to ``settings.py`` alone made every existing community test 500 with
   ``ImproperlyConfigured``. ``test_scopes_registered_in_both_settings`` locks
   that lesson in.

The most important assertion here is that the throttles do NOT apply to reads.
ThreadListView/ThreadDetailView allow anonymous GETs and DRF's UserRateThrottle
keys on IP when unauthenticated, so a naive UserRateThrottle would have capped
public forum browsing at the write rate for every logged-out visitor.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.throttling import UserRateThrottle

from common.throttles import (
    UgcLightThrottle,
    UgcReportThrottle,
    UgcUploadThrottle,
    UgcWriteThrottle,
)

User = get_user_model()

ALL_UGC = (UgcWriteThrottle, UgcLightThrottle, UgcUploadThrottle, UgcReportThrottle)


class _Req:
    """Minimal request stand-in — only .method is consulted on the safe path."""

    def __init__(self, method):
        self.method = method


class UgcThrottleLogicTests(TestCase):
    """Assert the short-circuit directly, independent of global throttle state.

    Patching UserRateThrottle.allow_request to raise proves whether our override
    delegated to it or returned early — which the test_settings monkey-patch
    would otherwise hide (it makes both paths return True).
    """

    def test_safe_methods_short_circuit_without_consuming_quota(self):
        boom = AssertionError("super().allow_request must not run for safe methods")
        for klass in ALL_UGC:
            for method in ("GET", "HEAD", "OPTIONS"):
                with self.subTest(throttle=klass.__name__, method=method):
                    with patch.object(UserRateThrottle, "allow_request", side_effect=boom):
                        self.assertTrue(klass().allow_request(_Req(method), None))

    def test_unsafe_methods_do_consume_quota(self):
        """Writes must reach the real rate limiter."""
        sentinel = object()
        for klass in ALL_UGC:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                with self.subTest(throttle=klass.__name__, method=method):
                    with patch.object(
                        UserRateThrottle, "allow_request", return_value=sentinel
                    ) as mocked:
                        result = klass().allow_request(_Req(method), None)
                    self.assertIs(result, sentinel)
                    self.assertEqual(mocked.call_count, 1)

    def test_scopes_registered_in_both_settings(self):
        """A scope missing from DEFAULT_THROTTLE_RATES raises ImproperlyConfigured.

        get_rate() is what blew up and 500'd every community endpoint when the
        scopes existed in settings.py but not test_settings.py.
        """
        for klass, scope in (
            (UgcWriteThrottle, "ugc_write"),
            (UgcLightThrottle, "ugc_light"),
            (UgcUploadThrottle, "ugc_upload"),
            (UgcReportThrottle, "ugc_report"),
        ):
            with self.subTest(scope=scope):
                self.assertEqual(klass.scope, scope)
                self.assertTrue(klass().get_rate(), f"{scope} has no configured rate")


class UgcThrottleWiringTests(TestCase):
    """Every community write view must actually declare a throttle."""

    def test_all_write_views_declare_a_throttle(self):
        from apps.community import views as cv

        expected = {
            "ThreadListView": UgcWriteThrottle,
            "ThreadDetailView": UgcWriteThrottle,
            "ReplyView": UgcWriteThrottle,
            "ReplyDetailView": UgcWriteThrottle,
            "VoteView": UgcLightThrottle,
            "ReplyReactionView": UgcLightThrottle,
            "ThreadAttachmentUploadView": UgcUploadThrottle,
            "ThreadReportView": UgcReportThrottle,
        }
        for name, throttle in expected.items():
            with self.subTest(view=name):
                view = getattr(cv, name)
                self.assertIn(
                    throttle,
                    getattr(view, "throttle_classes", []),
                    f"{name} is missing {throttle.__name__} — its write path is unbounded",
                )


class UgcReadPathTests(TestCase):
    """Reads must keep working. This is the regression that nearly shipped."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="ugc_tester", email="ugc@example.com", password="Str0ng-Pass-123"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def tearDown(self):
        cache.clear()

    def test_authenticated_reads_succeed(self):
        for _ in range(20):
            self.assertNotEqual(self.client.get("/api/community/threads/").status_code, 429)

    def test_anonymous_reads_succeed(self):
        anon = APIClient()
        for _ in range(30):
            self.assertNotEqual(anon.get("/api/community/threads/").status_code, 429)

    def test_writes_still_work_within_quota(self):
        resp = self.client.post(
            "/api/community/threads/",
            {"title": "Throttle smoke test", "body": "x" * 30},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", resp.status_code))
