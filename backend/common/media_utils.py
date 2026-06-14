"""Media URL helpers and strict image upload validation."""

from __future__ import annotations

import io
import logging
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

# Only these image purposes are accepted for uploads (no documents).
IMAGE_UPLOAD_SPECS: dict[str, dict[str, Any]] = {
    "promo_banner": {
        "width": 1200,
        "height": 280,
        "tolerance": 0.05,
        "help": "Promo banner image must be 1200×280 px (PNG, JPEG, or WebP only).",
    },
    "maintenance_banner": {
        "width": 1200,
        "height": 200,
        "tolerance": 0.05,
        "help": "Maintenance banner image must be 1200×200 px (PNG, JPEG, or WebP only).",
    },
    "community_screenshot": {
        "max_width": 1920,
        "max_height": 1080,
        "min_width": 200,
        "min_height": 120,
        "help": "Screenshot must be 200×120 to 1920×1080 px (PNG, JPEG, GIF, or WebP only).",
    },
}

ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "GIF", "WEBP"}


def public_media_url(url: str) -> str:
    """Return a browser-safe same-origin media path (/media/...)."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("data:"):
        return url
    if url.startswith("http://") or url.startswith("https://"):
        path = urlparse(url).path or ""
        if path.startswith("/media/"):
            return path
        return url
    if url.startswith("/media/"):
        return url
    if url.startswith("/"):
        return url
    base = (settings.MEDIA_URL or "/media/").rstrip("/")
    return f"{base}/{url.lstrip('/')}"


def _open_image(upload):
    from PIL import Image

    upload.seek(0)
    data = upload.read()
    upload.seek(0)
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ValueError("Invalid or corrupted image file.") from exc
    fmt = (img.format or "").upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValueError(f"Unsupported image format ({fmt or 'unknown'}). Use PNG, JPEG, GIF, or WebP.")
    return img, fmt


def validate_image_upload(upload, purpose: str) -> tuple[int, int]:
    """
    Validate file is an image and matches dimension rules for purpose.
    Returns (width, height).
    """
    spec = IMAGE_UPLOAD_SPECS.get(purpose)
    if not spec:
        raise ValueError(f"Unknown upload purpose: {purpose}")

    content_type = (getattr(upload, "content_type", "") or "").lower()
    if not content_type.startswith("image/"):
        raise ValueError("Only image files are allowed — no documents or other file types.")

    img, _fmt = _open_image(upload)
    width, height = img.size

    if "max_width" in spec:
        if width > spec["max_width"] or height > spec["max_height"]:
            raise ValueError(
                f"{spec['help']} Your file is {width}×{height} px."
            )
        if width < spec.get("min_width", 1) or height < spec.get("min_height", 1):
            raise ValueError(
                f"{spec['help']} Your file is {width}×{height} px."
            )
        return width, height

    target_w = spec["width"]
    target_h = spec["height"]
    tol = spec.get("tolerance", 0.05)
    w_ok = abs(width - target_w) <= max(1, int(target_w * tol))
    h_ok = abs(height - target_h) <= max(1, int(target_h * tol))
    if not (w_ok and h_ok):
        raise ValueError(
            f"{spec['help']} Your file is {width}×{height} px."
        )
    return width, height


def image_specs_for_api() -> dict:
    """Public dimension hints for admin UI."""
    return {
        key: {
            "help": spec["help"],
            **{k: spec[k] for k in ("width", "height", "max_width", "max_height", "min_width", "min_height") if k in spec},
        }
        for key, spec in IMAGE_UPLOAD_SPECS.items()
    }
