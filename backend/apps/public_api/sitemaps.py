"""Dynamic full-catalog sitemap.

Django's static frontend sitemap only listed ~10 marketing URLs, leaving the
entire catalog (thousands of scenarios, tutorials, projects, technology pages)
invisible to crawlers. These Sitemap classes expose the real public frontend
URL paths (served at /sitemap.xml through the nginx gateway) so search engines
can discover the whole catalog.

Notes:
  * The absolute URL host/scheme come from settings.SITE_URL (the public
    frontend origin) rather than django.contrib.sites, which is not installed.
  * Every section handles an empty/unseeded DB gracefully (querysets simply
    yield nothing) and uses .only()/lightweight fetches to stay efficient over
    the ~5.4k-row scenario table.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap


def _site_parts() -> tuple[str, str]:
    """Return (protocol, domain) parsed from settings.SITE_URL.

    Falls back to https + the first ALLOWED_HOSTS entry (or localhost) if
    SITE_URL is unset/malformed.
    """
    raw = getattr(settings, "SITE_URL", "") or ""
    parts = urlsplit(raw)
    protocol = parts.scheme or "https"
    domain = parts.netloc
    if not domain:
        allowed = [h for h in getattr(settings, "ALLOWED_HOSTS", []) if h not in ("*", "")]
        domain = allowed[0] if allowed else "localhost:8080"
    return protocol, domain


class _FrontendSitemap(Sitemap):
    """Base that resolves absolute URLs against settings.SITE_URL.

    django.contrib.sites is not installed, so we override get_urls() to inject a
    lightweight fake "site" object carrying the frontend host, and force the
    protocol from SITE_URL.
    """

    protocol = "https"

    def get_urls(self, page=1, site=None, protocol=None):
        proto, domain = _site_parts()
        fake_site = type("SiteShim", (), {"domain": domain, "name": domain})()
        return super().get_urls(page=page, site=fake_site, protocol=proto)


class StaticViewSitemap(_FrontendSitemap):
    """Public marketing / catalog-index routes with no per-object slug."""

    changefreq = "weekly"

    # {path: priority} — real routes from frontend/src/router/AppRouter.jsx
    ROUTES = {
        "/": 1.0,
        "/pricing": 0.7,
        "/about": 0.5,
        "/contact": 0.4,
        "/scenarios": 0.9,
        "/technologies": 0.9,
        "/tutorials": 0.8,
        "/certifications": 0.7,
        "/playgrounds": 0.6,
    }

    def items(self):
        return list(self.ROUTES)

    def location(self, item):
        return item

    def priority(self, item):
        return self.ROUTES.get(item, 0.6)


class TechnologySitemap(_FrontendSitemap):
    """Active (non-coming-soon) technology hub pages: /technologies/<slug>."""

    changefreq = "weekly"
    priority = 0.8

    def items(self):
        from apps.question_bank.models import Technology

        return list(
            Technology.objects.filter(is_active=True, coming_soon=False)
            .only("slug")
            .order_by("slug")
        )

    def location(self, obj):
        return f"/technologies/{obj.slug}"

    # Technology has no updated_at field — omit lastmod (returns None).
    def lastmod(self, obj):
        return None


class ScenarioSitemap(_FrontendSitemap):
    """Active scenarios: /scenarios/<slug>. This is the bulk of the catalog."""

    changefreq = "monthly"
    priority = 0.7
    limit = 5000  # Django paginates automatically past this many URLs

    def items(self):
        from apps.question_bank.models import Scenario

        return (
            Scenario.objects.filter(is_active=True)
            .only("slug", "updated_at")
            .order_by("slug")
        )

    def location(self, obj):
        return f"/scenarios/{obj.slug}"

    def lastmod(self, obj):
        return obj.updated_at


class TutorialSitemap(_FrontendSitemap):
    """Published tutorials: /tutorials/<slug>."""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        from apps.tutorials.models import Tutorial

        return (
            Tutorial.objects.filter(is_published=True)
            .only("slug", "updated_at")
            .order_by("slug")
        )

    def location(self, obj):
        return f"/tutorials/{obj.slug}"

    def lastmod(self, obj):
        return obj.updated_at


class ProjectSitemap(_FrontendSitemap):
    """Active projects.

    Projects have no dedicated public detail route — they surface inside the
    technology hub page and launch via an API action — so we emit the crawlable
    technology-detail URL each project lives on, de-duplicated so we never list
    the same technology twice or emit a URL for a coming-soon technology.
    """

    changefreq = "monthly"
    priority = 0.5

    def items(self):
        from apps.question_bank.models import Project

        seen: set[str] = set()
        ordered_slugs: list[str] = []
        qs = (
            Project.objects.filter(is_active=True, technology__coming_soon=False)
            .values_list("technology__slug", flat=True)
            .order_by("technology__slug")
        )
        for slug in qs:
            if slug and slug not in seen:
                seen.add(slug)
                ordered_slugs.append(slug)
        return ordered_slugs

    def location(self, slug):
        return f"/technologies/{slug}"

    def lastmod(self, slug):
        return None


SITEMAPS = {
    "static": StaticViewSitemap,
    "technologies": TechnologySitemap,
    "scenarios": ScenarioSitemap,
    "tutorials": TutorialSitemap,
    "projects": ProjectSitemap,
}
