"""
Community admin — Thread, Reply, ThreadAttachment.
"""
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Reply, Thread, ThreadAttachment


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
