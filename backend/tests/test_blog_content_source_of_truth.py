"""Audit Z3-12 — the blog had two sources of truth and the wrong one won.

`BlogPost.jsx` carried ~700 lines of article prose and preferred it over the API
whenever the stored body was under 200 characters. Migration 0006 seeded only
three posts, each a short stub — which is *why* that override existed, and why
editing a post in the admin appeared to do nothing: a genuine edit shorter than
the bundled copy was silently discarded.

Five of the eight posts existed only in the bundle, so simply deleting it would
have 404'd them. Migration 0010 writes the full text of all eight into the
database, the frontend now treats the database as authoritative, and the bundled
copy became a dynamically-imported offline fallback (a 10 kB chunk fetched only
when the API cannot answer, rather than prose shipped to every visitor).

The admin CRUD had a related defect on both write paths: `slug` is `unique=True`
and both `create()` and the `patch` handler wrote straight through, so a duplicate
title was an `IntegrityError` surfacing as a 500 rather than a 409.
"""
import pathlib
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.adminpanel.models import BlogPost

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


class TheDatabaseHasTheRealProseTests(TestCase):
    """Migration 0010 runs as part of building the test database, so these assert
    against migrated state rather than re-running the migration by hand."""

    def test_every_bundled_post_exists_in_the_database(self):
        expected = {
            "why-hands-on-learning-works", "debugging-nginx-like-a-pro",
            "docker-vs-cloud-labs", "top-5-linux-troubleshooting-commands",
            "building-fixitlab-architecture", "dns-troubleshooting-guide",
            "kubernetes-crashloop-debugging", "teams-coupons-and-security",
        }
        missing = expected - set(BlogPost.objects.values_list("slug", flat=True))
        self.assertEqual(
            missing, set(),
            f"these posts exist only in the JS bundle, so removing it would 404 "
            f"them: {sorted(missing)}",
        )

    def test_the_content_is_real_prose_not_a_stub(self):
        """The three posts seeded by 0006 were short stubs. If they still are, the
        frontend has nothing to render and the fallback is load-bearing again."""
        for post in BlogPost.objects.all():
            self.assertGreater(
                len(post.content or ""), 1500,
                f"'{post.slug}' has only {len(post.content or '')} characters — "
                "still a stub",
            )

    def test_posts_are_published_and_have_an_excerpt(self):
        for post in BlogPost.objects.all():
            self.assertTrue(post.is_published, post.slug)
            self.assertTrue((post.excerpt or "").strip(), post.slug)


class TheMigrationDoesNotClobberEditsTests(TestCase):
    """A data migration that overwrites an editor's work is worse than the bug it
    fixes. Verified by reading the migration's own logic, since it has already run
    against this database."""

    def test_it_skips_a_post_that_is_already_longer(self):
        src = (
            pathlib.Path(__file__).resolve().parent.parent
            / "apps" / "adminpanel" / "migrations" / "0010_blog_content_to_db.py"
        ).read_text()
        self.assertIn("len(existing.content", src)
        self.assertIn(">= len(row[", src)

    def test_the_reverse_is_a_no_op_not_a_delete(self):
        """Rolling back must not destroy content an editor may have changed."""
        src = (
            pathlib.Path(__file__).resolve().parent.parent
            / "apps" / "adminpanel" / "migrations" / "0010_blog_content_to_db.py"
        ).read_text()
        reverse = re.search(r"def noop\(apps, schema_editor\):(.*?)(?=\nclass |\Z)", src, re.S)
        self.assertIsNotNone(reverse)
        self.assertNotIn("delete(", reverse.group(1))


class _AdminBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="blogadmin", email="blogadmin@example.com", password=PASSWORD,
            is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.list_url = "/api/admin/blog/"

    def _create(self, **body):
        payload = {"title": "A Post", "content": "body"}
        payload.update(body)
        return self.client.post(self.list_url, payload, format="json")


class DuplicateSlugIsA409NotA500Tests(_AdminBase):
    def test_the_route_is_wired(self):
        from django.urls import resolve

        self.assertEqual(
            resolve(self.list_url).func.view_class.__name__, "AdminBlogPostsView"
        )

    def test_a_first_post_is_created(self):
        resp = self._create(title="Unique Title Here")
        self.assertEqual(resp.status_code, 201, getattr(resp, "data", resp))

    def test_a_duplicate_title_is_refused_cleanly(self):
        self._create(title="Same Title")
        resp = self._create(title="Same Title")
        self.assertEqual(
            resp.status_code, 409,
            "a duplicate slug still raises IntegrityError and surfaces as a 500",
        )
        self.assertIn("already exists", str(resp.data))

    def test_the_duplicate_did_not_create_a_row(self):
        self._create(title="Only Once")
        self._create(title="Only Once")
        self.assertEqual(BlogPost.objects.filter(slug="only-once").count(), 1)

    def test_a_title_with_no_slugifiable_characters_is_refused(self):
        """slugify('!!!') is '' and slug is unique, so the first such post would
        take the empty slug and every one after it would collide."""
        resp = self._create(title="!!! ???")
        self.assertEqual(resp.status_code, 400)

    def test_renaming_onto_an_existing_slug_is_refused(self):
        first = self._create(title="First Post").data
        second = self._create(title="Second Post").data
        resp = self.client.patch(
            f"/api/admin/blog/{second['id']}/", {"slug": first["slug"]}, format="json"
        )
        self.assertEqual(
            resp.status_code, 409,
            "renaming a post onto an existing URL still 500s",
        )

    def test_saving_a_post_without_changing_its_slug_still_works(self):
        """Guard the guard: excluding the post itself from the uniqueness check is
        what stops it reporting a conflict with itself."""
        created = self._create(title="Keeps Its Slug").data
        resp = self.client.patch(
            f"/api/admin/blog/{created['id']}/",
            {"slug": created["slug"], "title": "Retitled"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))

    def test_an_empty_slug_on_update_is_refused(self):
        created = self._create(title="Has A Slug").data
        resp = self.client.patch(
            f"/api/admin/blog/{created['id']}/", {"slug": "   "}, format="json"
        )
        self.assertEqual(resp.status_code, 400)
