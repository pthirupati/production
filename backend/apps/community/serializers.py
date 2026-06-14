from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.html import strip_tags
from .models import Thread, Reply, ThreadVote, ThreadAttachment, ReplyReaction

User = get_user_model()


def sanitize_text(value):
    """Strip HTML tags to prevent XSS in community content."""
    if value:
        return strip_tags(value).strip()
    return value


class ThreadAuthorSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    is_premium = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "is_premium"]

    def get_username(self, obj):
        return obj.username or obj.email.split("@")[0]

    def get_is_premium(self, obj):
        try:
            return hasattr(obj, "subscription") and obj.subscription.plan.code != "free"
        except Exception:
            return False


class ThreadAttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    uploader = serializers.CharField(source="uploaded_by.username", read_only=True)

    class Meta:
        model = ThreadAttachment
        fields = ["id", "url", "original_name", "content_type", "uploader", "created_at"]

    def get_url(self, obj):
        from common.media_utils import public_media_url
        if not obj.file:
            return ""
        return public_media_url(obj.file.url)


class ReplySerializer(serializers.ModelSerializer):
    author = ThreadAuthorSerializer(read_only=True)
    children = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()
    attachments = ThreadAttachmentSerializer(many=True, read_only=True)
    reactions = serializers.SerializerMethodField()
    user_reactions = serializers.SerializerMethodField()

    class Meta:
        model = Reply
        fields = [
            "id", "thread", "author", "parent", "body",
            "upvotes", "is_deleted", "created_at", "updated_at",
            "children", "user_vote", "attachments", "reactions", "user_reactions",
        ]
        read_only_fields = ["id", "thread", "author", "upvotes", "is_deleted", "created_at", "updated_at"]

    def get_children(self, obj):
        children = obj.children.filter(is_deleted=False).select_related("author")
        return ReplySerializer(children, many=True, context=self.context).data

    def get_user_vote(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            vote = ThreadVote.objects.filter(user=request.user, reply=obj).first()
            return vote.vote_type if vote else None
        return None

    def get_reactions(self, obj):
        from django.db.models import Count
        rows = obj.reactions.values("emoji").annotate(count=Count("id"))
        return {row["emoji"]: row["count"] for row in rows}

    def get_user_reactions(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return []
        return list(
            obj.reactions.filter(user=request.user).values_list("emoji", flat=True)
        )

    def validate_body(self, value):
        return sanitize_text(value)


class ThreadListSerializer(serializers.ModelSerializer):
    author = ThreadAuthorSerializer(read_only=True)
    technology_name = serializers.CharField(source="technology.name", read_only=True, default=None)
    user_vote = serializers.SerializerMethodField()
    attachments = ThreadAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Thread
        fields = [
            "id", "author", "title", "body", "technology", "technology_name",
            "is_pinned", "is_locked", "upvotes", "reply_count",
            "created_at", "updated_at", "user_vote", "attachments",
        ]
        read_only_fields = [
            "id", "author", "is_pinned", "is_locked",
            "upvotes", "reply_count", "created_at", "updated_at",
        ]

    def get_user_vote(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            vote = ThreadVote.objects.filter(user=request.user, thread=obj).first()
            return vote.vote_type if vote else None
        return None

    def validate_title(self, value):
        return sanitize_text(value)

    def validate_body(self, value):
        return sanitize_text(value)


class ThreadDetailSerializer(ThreadListSerializer):
    replies = serializers.SerializerMethodField()

    class Meta(ThreadListSerializer.Meta):
        fields = ThreadListSerializer.Meta.fields + ["replies"]

    def get_replies(self, obj):
        top_level = obj.replies.filter(parent__isnull=True, is_deleted=False).select_related("author")
        return ReplySerializer(top_level, many=True, context=self.context).data
