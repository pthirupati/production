from django.contrib import admin
from .models import Thread, Reply


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "technology", "is_pinned", "is_locked", "reply_count", "created_at"]
    list_filter = ["is_pinned", "is_locked", "is_deleted", "technology"]
    search_fields = ["title", "body", "author__username"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ["__str__", "author", "thread", "is_deleted", "created_at"]
    list_filter = ["is_deleted"]
    search_fields = ["body", "author__username"]
