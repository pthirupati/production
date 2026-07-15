"""Regression tests for community thread image attachments.

BUG: uploaded thread images did not render and the returned URL 404'd. Root
cause was in the 4-droplet topology — the edge gateway (D1) served /media/ from
an empty, per-host Docker volume that was never synced from the App node (D2)
that actually stored uploads. The fix proxies /media/ from the edge to the App
backend AND makes the App backend serve /media/ via Django even with DEBUG=False
(SERVE_MEDIA + a static-serve route that does not short-circuit on DEBUG).

These tests exercise the end-to-end contract that broke: upload an image via the
community attachment API, then fetch the URL the API returns through the Django
test client and assert it is served (200) — including under the production-shaped
settings (DEBUG=False, SERVE_MEDIA=True) where the old django.conf.urls.static
helper silently returned nothing.
"""
import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.community.models import Thread

User = get_user_model()

_MEDIA_TMP = tempfile.mkdtemp(prefix="fixitlab-media-test-")


def _png_bytes(width=400, height=300):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (10, 120, 200)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def _upload_file(name="shot.png", width=400, height=300):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, _png_bytes(width, height).read(), content_type="image/png")


@override_settings(JWT_SESSION_ENFORCEMENT=False, MEDIA_ROOT=_MEDIA_TMP)
class ThreadAttachmentMediaTest(APITestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_MEDIA_TMP, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="uploader", email="uploader@example.com", password="pw-Str0ng!23"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.thread = Thread.objects.create(author=self.user, title="screenshot thread", body="see image")

    def _upload(self):
        resp = self.client.post(
            f"/api/community/threads/{self.thread.id}/attachments/",
            {"file": _upload_file()},
            format="multipart",
        )
        assert resp.status_code == 201, (resp.status_code, dict(resp.data))
        url = resp.data["url"]
        assert url.startswith("/media/"), url
        return url

    def test_upload_then_fetch_url_returns_200(self):
        """The core bug: the URL the API hands back must actually serve the image."""
        url = self._upload()
        fetched = self.client.get(url)
        assert fetched.status_code == 200, (fetched.status_code, url)

    @override_settings(DEBUG=False, SERVE_MEDIA=True)
    def test_media_served_in_production_settings(self):
        """DEBUG=False + SERVE_MEDIA=True (the App-node/cluster posture) must still
        serve /media/. Guards against django.conf.urls.static() short-circuiting
        to [] when DEBUG is False, which reintroduces the 404."""
        # urls.py wires the media route at import time based on settings, so
        # re-import the URLConf under the overridden settings.
        from importlib import reload
        from django.urls import clear_url_caches
        import config.urls as urlconf

        reload(urlconf)
        clear_url_caches()
        try:
            url = self._upload()
            fetched = self.client.get(url)
            assert fetched.status_code == 200, (fetched.status_code, url)
        finally:
            reload(urlconf)
            clear_url_caches()

    def test_rejects_non_image_upload(self):
        """Uploads stay image-only."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad = SimpleUploadedFile("notes.txt", b"hello world", content_type="text/plain")
        resp = self.client.post(
            f"/api/community/threads/{self.thread.id}/attachments/",
            {"file": bad},
            format="multipart",
        )
        assert resp.status_code == 400, (resp.status_code, dict(resp.data))
