"""
Scenario version history admin.

This table was write-only: a post_save receiver in question_bank/apps.py
appended a JSON snapshot per Scenario save and nothing ever read it back
(audit B7). It is the only change history for scenario definitions, so the
fix is a reader rather than a drop. Read-only by design — versions are an
audit trail, and hand-editing one would make it worthless.
"""
import json

from django.contrib import admin
from django.utils.html import format_html

from .models import ScenarioVersion
from .utils import get_version_history


@admin.register(ScenarioVersion)
class ScenarioVersionAdmin(admin.ModelAdmin):
    list_display = ("scenario", "version", "is_active", "created_at", "summary")
    list_filter = ("is_active", "created_at")
    search_fields = ("scenario__slug", "scenario__title", "definition_path")
    date_hierarchy = "created_at"
    list_select_related = ("scenario",)
    readonly_fields = (
        "scenario",
        "version",
        "definition_path",
        "is_active",
        "created_at",
        "position",
        "snapshot",
    )
    exclude = ("changelog",)

    @admin.display(description="Title at this version")
    def summary(self, obj):
        """The snapshotted title, which is what makes one version legible next
        to another in the changelist."""
        snapshot = self._parse(obj)
        if snapshot is None:
            return "—"
        return snapshot.get("title") or "—"

    @admin.display(description="Position in history")
    def position(self, obj):
        """Where this row sits in its scenario's history, e.g. "v3 of 7"."""
        total = get_version_history(obj.scenario).count()
        return f"v{obj.version} of {total}"

    @admin.display(description="Snapshot")
    def snapshot(self, obj):
        """Pretty-print the stored JSON definition for the detail page."""
        snapshot = self._parse(obj)
        if snapshot is None:
            # Older rows predate the JSON snapshot format; show them verbatim
            # rather than hiding the content behind a parse error.
            return format_html("<pre>{}</pre>", obj.changelog or "")
        return format_html("<pre>{}</pre>", json.dumps(snapshot, indent=2, sort_keys=True))

    @staticmethod
    def _parse(obj):
        try:
            parsed = json.loads(obj.changelog or "")
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
