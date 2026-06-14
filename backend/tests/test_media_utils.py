"""Media URL and image validation tests."""
import io
from django.test import SimpleTestCase

from common.media_utils import public_media_url, validate_image_upload


class PublicMediaUrlTest(SimpleTestCase):
    def test_relative_media_path(self):
        self.assertEqual(public_media_url("/media/platform/x.png"), "/media/platform/x.png")

    def test_rewrites_internal_absolute_url(self):
        url = public_media_url("http://backend:8000/media/community/a.png")
        self.assertEqual(url, "/media/community/a.png")


class ImageValidationTest(SimpleTestCase):
    def _png(self, width, height):
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (width, height), color="red").save(buf, format="PNG")
        buf.seek(0)
        buf.content_type = "image/png"
        buf.name = "test.png"
        return buf

    def test_promo_banner_exact_dimensions(self):
        f = self._png(1200, 280)
        w, h = validate_image_upload(f, "promo_banner")
        self.assertEqual((w, h), (1200, 280))

    def test_promo_banner_rejects_wrong_size(self):
        f = self._png(800, 200)
        with self.assertRaises(ValueError) as ctx:
            validate_image_upload(f, "promo_banner")
        self.assertIn("1200×280", str(ctx.exception))

    def test_community_accepts_screenshot_range(self):
        f = self._png(800, 600)
        w, h = validate_image_upload(f, "community_screenshot")
        self.assertEqual((w, h), (800, 600))
