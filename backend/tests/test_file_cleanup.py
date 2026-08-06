"""Deleting a row must delete its blob, not just the database record.

Django deletes the ROW, never the file. With no django-cleanup and no post_delete
handlers, every upload outlived its record: `interviews/resumes/` and
`interviews/async_video/` survived `user.delete()` on disk while the rows vanished
(audit Z4-3). For a platform whose privacy policy promises deletion, and whose most
sensitive data class is candidate resumes and interview video, "the row is gone" is
not deletion.

The replace path matters just as much and is easier to miss: re-uploading a resume
writes a new name and orphans the old file forever. Nothing references it, nothing
removes it, and it accumulates silently on a live system.
"""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from apps.interviews.models import CandidateProfile

User = get_user_model()
_TMP_MEDIA = tempfile.mkdtemp(prefix="fixitlab_media_test_")


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class ResumeBlobLifecycleTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="blobber", email="blob@example.com", password="Str0ng-Pass-1"
        )
        self.profile = CandidateProfile.objects.create(user=self.user)
        self.profile.resume_file.save(
            "cv.txt", ContentFile(b"Jane Doe - senior engineer"), save=True
        )
        self.storage = self.profile.resume_file.storage
        self.name = self.profile.resume_file.name

    def test_fixture_actually_wrote_a_file(self):
        """Guard the premise — if the upload silently no-ops these tests are vacuous."""
        self.assertTrue(self.storage.exists(self.name))

    def test_deleting_the_row_deletes_the_resume(self):
        self.profile.delete()
        self.assertFalse(
            self.storage.exists(self.name),
            "the resume survived deletion of its row",
        )

    def test_deleting_the_user_deletes_the_resume(self):
        """The path the privacy policy actually promises."""
        self.user.delete()
        self.assertFalse(
            self.storage.exists(self.name),
            "the resume survived user.delete() — 'we delete your data' was false",
        )

    def test_replacing_the_resume_removes_the_previous_file(self):
        old = self.name
        self.profile.resume_file.save(
            "cv2.txt", ContentFile(b"Jane Doe - staff engineer"), save=True
        )
        new = self.profile.resume_file.name
        self.assertNotEqual(old, new)
        self.assertTrue(self.storage.exists(new), "the new resume was not stored")
        self.assertFalse(
            self.storage.exists(old),
            "the previous resume was orphaned on disk — this accumulates forever",
        )

    def test_saving_an_unrelated_field_keeps_the_file(self):
        """The replace handler must fire on CHANGE, not on every save."""
        self.profile.resume_text = "parsed later"
        self.profile.save()
        self.assertTrue(
            self.storage.exists(self.name),
            "an unrelated save deleted the resume the row still points at",
        )

    def test_row_without_a_file_deletes_cleanly(self):
        """blank=True/null=True — deletion must not raise on an empty FileField."""
        u = User.objects.create_user(
            username="nofile", email="nofile@example.com", password="Str0ng-Pass-1"
        )
        p = CandidateProfile.objects.create(user=u)
        p.delete()  # must not raise
        self.assertFalse(CandidateProfile.objects.filter(pk=p.pk).exists())

    def test_missing_file_on_disk_does_not_block_deletion(self):
        """A blob already gone (manual cleanup, restored DB) must not wedge delete."""
        self.storage.delete(self.name)
        self.profile.delete()  # must not raise
        self.assertFalse(CandidateProfile.objects.filter(pk=self.profile.pk).exists())

    def test_queryset_delete_also_removes_blobs(self):
        """Bulk delete still emits post_delete, and admin/moderation uses it."""
        CandidateProfile.objects.filter(pk=self.profile.pk).delete()
        self.assertFalse(self.storage.exists(self.name))


class RegistrationCoverageTests(TestCase):
    """Every FileField/ImageField on the platform should be registered, or the next
    upload field silently reintroduces the leak."""

    def test_all_file_fields_have_cleanup_registered(self):
        from django.apps import apps as django_apps
        from django.db.models import FileField
        from django.db.models.signals import post_delete

        missing = []
        for model in django_apps.get_models():
            file_fields = [
                f.name for f in model._meta.get_fields()
                if isinstance(f, FileField)
            ]
            if not file_fields:
                continue
            uid = f"file_cleanup_delete:{model._meta.label_lower}"
            registered = any(
                r[0] == (uid, id(model)) or (isinstance(r[0], tuple) and r[0][0] == uid)
                for r in post_delete.receivers
            )
            if not registered:
                missing.append(f"{model._meta.label} ({', '.join(file_fields)})")
        self.assertEqual(
            missing, [],
            "these models store files with no cleanup — the blobs will outlive "
            "their rows: " + "; ".join(missing),
        )
