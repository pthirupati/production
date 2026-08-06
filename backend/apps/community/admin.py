"""
Community admin — Thread, Reply, ThreadAttachment, ThreadReport.
"""
from django.contrib import admin, messages
from django.utils.html import format_html

from django.db.models import Count, Q

from .models import Reply, Thread, ThreadAttachment, ThreadReport


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class ModerationFilter(admin.SimpleListFilter):
    """Threads that need moderation: deleted OR neither pinned/locked yet high reply count."""
    title = "moderation needed"
    parameter_name = "mod"

    def lookups(self, request, model_admin):
        return [
            ("deleted", "Soft-deleted"),
            ("active", "Active (not deleted)"),
        ]

    def queryset(self, qs, value):
        if value == "deleted":
            return qs.filter(is_deleted=True)
        if value == "active":
            return qs.filter(is_deleted=False)
        return qs


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class ReplyInline(admin.TabularInline):
    model = Reply
    fields = ("author", "body_preview", "is_deleted", "upvotes", "created_at")
    readonly_fields = ("author", "body_preview", "upvotes", "created_at")
    extra = 0
    can_delete = True
    ordering = ("created_at",)

    @admin.display(description="Body")
    def body_preview(self, obj):
        return obj.body[:100]


class ThreadAttachmentInline(admin.TabularInline):
    model = ThreadAttachment
    fields = ("uploaded_by", "original_name", "content_type", "file", "created_at")
    readonly_fields = ("uploaded_by", "original_name", "content_type", "created_at")
    extra = 0
    can_delete = True


# ---------------------------------------------------------------------------
# Thread admin
# ---------------------------------------------------------------------------

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = (
        "title_truncated",
        "author",
        "technology",
        "open_reports",
        "upvotes",
        "reply_count",
        "is_pinned",
        "is_locked",
        "is_deleted",
        "created_at",
    )
    list_filter = (
        ModerationFilter,
        "is_pinned",
        "is_locked",
        "technology",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("title", "body", "author__username", "author__email")
    readonly_fields = ("id", "created_at", "updated_at", "upvotes", "reply_count")
    list_select_related = ("author", "technology")
    date_hierarchy = "created_at"
    list_per_page = 50
    inlines = [ReplyInline, ThreadAttachmentInline]
    actions = [
        "action_pin",
        "action_unpin",
        "action_lock",
        "action_unlock",
        "action_soft_delete",
        "action_restore",
    ]

    @admin.display(description="Title")
    def title_truncated(self, obj):
        deleted = " [DELETED]" if obj.is_deleted else ""
        return format_html(
            "<span style='color:{}'>{}{}</span>",
            "grey" if obj.is_deleted else "inherit",
            obj.title[:60],
            deleted,
        )

    def get_queryset(self, request):
        # Surface report pressure where moderators actually look. Without this the
        # only way to find a reported thread was to open the (previously
        # unregistered) ThreadReport changelist. Annotated rather than counted
        # per row to avoid an N+1 across the changelist.
        return super().get_queryset(request).annotate(
            _open_reports=Count(
                "reports", filter=Q(reports__status="open"), distinct=True,
            )
        )

    @admin.display(description="Reports", ordering="_open_reports")
    def open_reports(self, obj):
        n = getattr(obj, "_open_reports", 0) or 0
        if not n:
            return "—"
        colour = "#b91c1c" if n > 1 else "#d97706"
        return format_html(
            '<a href="/admin/community/threadreport/?thread__id__exact={}" '
            'style="color:{};font-weight:700">{}</a>',
            obj.id, colour, n,
        )

    @admin.action(description="Pin selected threads")
    def action_pin(self, request, queryset):
        queryset.update(is_pinned=True)
        self.message_user(request, "Threads pinned.", messages.SUCCESS)

    @admin.action(description="Unpin selected threads")
    def action_unpin(self, request, queryset):
        queryset.update(is_pinned=False)
        self.message_user(request, "Threads unpinned.", messages.SUCCESS)

    @admin.action(description="Lock selected threads (prevent replies)")
    def action_lock(self, request, queryset):
        queryset.update(is_locked=True)
        self.message_user(request, "Threads locked.", messages.WARNING)

    @admin.action(description="Unlock selected threads")
    def action_unlock(self, request, queryset):
        queryset.update(is_locked=False)
        self.message_user(request, "Threads unlocked.", messages.SUCCESS)

    @admin.action(description="Soft-delete selected threads")
    def action_soft_delete(self, request, queryset):
        queryset.update(is_deleted=True)
        self.message_user(request, "Threads soft-deleted.", messages.WARNING)

    @admin.action(description="Restore (un-delete) selected threads")
    def action_restore(self, request, queryset):
        queryset.update(is_deleted=False)
        self.message_user(request, "Threads restored.", messages.SUCCESS)


# ---------------------------------------------------------------------------
# Reply admin
# ---------------------------------------------------------------------------

@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("body_preview", "author", "thread_link", "is_deleted", "upvotes", "created_at")
    list_filter = ("is_deleted", ("created_at", admin.DateFieldListFilter))
    search_fields = ("body", "author__username", "thread__title")
    readonly_fields = ("id", "thread", "author", "parent", "upvotes", "created_at", "updated_at")
    list_select_related = ("author", "thread")
    date_hierarchy = "created_at"
    actions = ["action_soft_delete", "action_restore"]

    @admin.display(description="Body")
    def body_preview(self, obj):
        return obj.body[:80]

    @admin.display(description="Thread")
    def thread_link(self, obj):
        return format_html(
            '<a href="/admin/community/thread/{}/change/">{}</a>',
            obj.thread_id,
            str(obj.thread)[:40],
        )

    @admin.action(description="Soft-delete selected replies")
    def action_soft_delete(self, request, queryset):
        queryset.update(is_deleted=True)
        self.message_user(request, "Replies soft-deleted.", messages.WARNING)

    @admin.action(description="Restore selected replies")
    def action_restore(self, request, queryset):
        queryset.update(is_deleted=False)
        self.message_user(request, "Replies restored.", messages.SUCCESS)


# ---------------------------------------------------------------------------
# Attachment admin
# ---------------------------------------------------------------------------

@admin.register(ThreadAttachment)
class ThreadAttachmentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "uploaded_by", "content_type", "thread", "reply", "created_at")
    list_filter = ("content_type",)
    search_fields = ("original_name", "uploaded_by__username")
    readonly_fields = ("id", "uploaded_by", "thread", "reply", "file", "original_name", "content_type", "created_at")
    list_select_related = ("uploaded_by", "thread")


# ---------------------------------------------------------------------------
# Moderation queue
# ---------------------------------------------------------------------------
class OpenReportFilter(admin.SimpleListFilter):
    """Default the changelist to reports that still need a decision."""

    title = "review state"
    parameter_name = "review"

    def lookups(self, request, model_admin):
        return (("open", "Needs review"), ("closed", "Reviewed or dismissed"))

    def queryset(self, request, queryset):
        if self.value() == "open":
            return queryset.filter(status="open")
        if self.value() == "closed":
            return queryset.exclude(status="open")
        return queryset


@admin.register(ThreadReport)
class ThreadReportAdmin(admin.ModelAdmin):
    """Moderation queue for user-submitted abuse reports.

    ThreadReport was a well-modelled table that NOTHING read. It had reason
    choices, a status workflow and a unique-per-reporter constraint, and the write
    path worked — but it was never registered here and has no adminpanel endpoint,
    so `status` sat at "open" forever. Reporting abuse did literally nothing, and
    moderation was "an admin happens to scroll the recent-threads list".

    Kept read-mostly on purpose: a report is a record of what a user said, so the
    reason, details, reporter and thread are immutable here. Only `status` is
    editable, because that is the moderator's decision rather than the user's claim.
    """

    list_display = (
        "created_at", "reason", "status", "thread_link",
        "reporter_email", "other_reports", "details_preview",
    )
    list_filter = (OpenReportFilter, "status", "reason", "created_at")
    search_fields = ("thread__title", "reporter__email", "reporter__username", "details")
    readonly_fields = ("id", "thread", "reporter", "reason", "details", "created_at")
    list_select_related = ("thread", "reporter")
    date_hierarchy = "created_at"
    actions = ("action_mark_reviewed", "action_dismiss")

    def get_queryset(self, request):
        # other_reports would otherwise be one query per row.
        return super().get_queryset(request).annotate(
            _sibling_reports=Count(
                "thread__reports", filter=Q(thread__reports__status="open"), distinct=True,
            )
        )

    @admin.display(description="Thread")
    def thread_link(self, obj):
        if not obj.thread_id:
            return "—"
        return format_html(
            '<a href="/admin/community/thread/{}/change/">{}</a>',
            obj.thread_id, (obj.thread.title or "(untitled)")[:60],
        )

    @admin.display(description="Reporter")
    def reporter_email(self, obj):
        return getattr(obj.reporter, "email", None) or getattr(obj.reporter, "username", "—")

    @admin.display(description="Open reports on thread", ordering="_sibling_reports")
    def other_reports(self, obj):
        """A thread with several open reports is the one to look at first."""
        n = getattr(obj, "_sibling_reports", 0) or 0
        if n > 1:
            return format_html('<b style="color:#b91c1c">{}</b>', n)
        return n

    @admin.display(description="Details")
    def details_preview(self, obj):
        text = (obj.details or "").strip()
        return (text[:80] + "…") if len(text) > 80 else (text or "—")

    @admin.action(description="Mark selected reports reviewed")
    def action_mark_reviewed(self, request, queryset):
        n = queryset.update(status="reviewed")
        messages.success(request, f"{n} report(s) marked reviewed.")

    @admin.action(description="Dismiss selected reports (no action needed)")
    def action_dismiss(self, request, queryset):
        n = queryset.update(status="dismissed")
        messages.success(request, f"{n} report(s) dismissed.")
