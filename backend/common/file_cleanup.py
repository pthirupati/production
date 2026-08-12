"""Delete stored blobs when their row is deleted or their field is replaced.

Django deletes the ROW, never the file. With no `django-cleanup` and no
`post_delete` handlers, every uploaded blob outlived its record — so
`interviews/resumes/` and `interviews/async_video/` survived `user.delete()` on
disk while the database rows vanished (audit Z4-3). For a platform whose privacy
policy promises deletion, and whose most sensitive data class is candidate resumes
and interview video, "the row is gone" is not deletion.

Two leaks, not one:

* **delete** — the obvious case, the row goes and the file stays.
* **replace** — a learner re-uploading a resume orphans the previous file under a
  different name. Nothing ever referenced it again, and nothing ever removed it.
  This one silently accumulates on a live system.

Deliberately best-effort: a storage error must never block a deletion the user
asked for, or leave a half-deleted row behind. We log and move on — an orphaned
blob is recoverable, a failed account deletion is a compliance problem.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_delete, pre_save

logger = logging.getLogger(__name__)


def _delete_blob(fieldfile) -> None:
    """Remove the underlying file for a FieldFile, tolerating anything."""
    name = getattr(fieldfile, "name", "") or ""
    if not name:
        return
    try:
        storage = fieldfile.storage
    except Exception:  # pragma: no cover - detached file object
        return
    try:
        # exists() first so a missing file is not an error path; some storages
        # raise on delete() of a missing key.
        if storage.exists(name):
            storage.delete(name)
    except Exception as exc:  # pragma: no cover - best effort by design
        logger.warning("file_cleanup: could not delete %s: %s", name, exc)


def register_file_cleanup(model, *field_names: str) -> None:
    """Delete `field_names` blobs when a `model` row is deleted or replaced.

    Signals are keyed by dispatch_uid so a double registration (autoreload, or an
    app whose ready() runs twice under some runners) cannot double-delete.
    """
    label = model._meta.label_lower

    def _on_delete(sender, instance, **kwargs):
        for field in field_names:
            _delete_blob(getattr(instance, field, None))

    def _on_replace(sender, instance, **kwargs):
        if not instance.pk:
            return  # new row, nothing to replace
        try:
            previous = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            return
        for field in field_names:
            old = getattr(previous, field, None)
            new = getattr(instance, field, None)
            old_name = getattr(old, "name", "") or ""
            new_name = getattr(new, "name", "") or ""
            # Only when it actually changed — saving an unrelated field must not
            # delete the file the row still points at.
            if old_name and old_name != new_name:
                _delete_blob(old)

    post_delete.connect(
        _on_delete, sender=model, weak=False,
        dispatch_uid=f"file_cleanup_delete:{label}",
    )
    pre_save.connect(
        _on_replace, sender=model, weak=False,
        dispatch_uid=f"file_cleanup_replace:{label}",
    )
