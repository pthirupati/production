import logging
from django.db import models, transaction
from django.db.models import F
from django.db.models.functions import Greatest
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from .models import Thread, Reply, ThreadVote
from .serializers import (
    ThreadListSerializer,
    ThreadDetailSerializer,
    ReplySerializer,
)

logger = logging.getLogger(__name__)


class ThreadPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class ThreadListView(APIView):
    """List threads or create a new thread."""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        threads = Thread.objects.filter(is_deleted=False).select_related("author", "technology")

        # Filter by technology
        tech = request.query_params.get("technology")
        if tech:
            threads = threads.filter(technology__slug=tech)

        # Search
        search = request.query_params.get("search")
        if search:
            threads = threads.filter(
                models.Q(title__icontains=search) | models.Q(body__icontains=search)
            )

        paginator = ThreadPagination()
        page = paginator.paginate_queryset(threads, request)
        serializer = ThreadListSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=http_status.HTTP_401_UNAUTHORIZED,
            )
        serializer = ThreadListSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user)
        return Response(serializer.data, status=http_status.HTTP_201_CREATED)


class ThreadDetailView(APIView):
    """Get, update, or delete a thread."""
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, thread_id):
        try:
            thread = Thread.objects.select_related("author", "technology").get(
                id=thread_id, is_deleted=False
            )
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=http_status.HTTP_404_NOT_FOUND)

        serializer = ThreadDetailSerializer(thread, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, thread_id):
        try:
            thread = Thread.objects.get(id=thread_id, is_deleted=False)
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=http_status.HTTP_404_NOT_FOUND)

        # Only author or admin can edit
        if thread.author != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=http_status.HTTP_403_FORBIDDEN)

        allowed_fields = ["title", "body"]
        if request.user.is_staff:
            allowed_fields.extend(["is_pinned", "is_locked"])

        for field in allowed_fields:
            if field in request.data:
                setattr(thread, field, request.data[field])
        thread.save()

        serializer = ThreadDetailSerializer(thread, context={"request": request})
        return Response(serializer.data)

    def delete(self, request, thread_id):
        try:
            thread = Thread.objects.get(id=thread_id, is_deleted=False)
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=http_status.HTTP_404_NOT_FOUND)

        # Only author or admin can delete
        if thread.author != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=http_status.HTTP_403_FORBIDDEN)

        thread.is_deleted = True
        thread.save(update_fields=["is_deleted"])
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class ReplyView(APIView):
    """Create a reply to a thread."""
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id):
        try:
            thread = Thread.objects.get(id=thread_id, is_deleted=False)
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=http_status.HTTP_404_NOT_FOUND)

        if thread.is_locked and not request.user.is_staff:
            return Response(
                {"error": "This thread is locked"},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        serializer = ReplySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user, thread=thread)

        # Update reply count
        Thread.objects.filter(id=thread_id).update(reply_count=F("reply_count") + 1)

        return Response(serializer.data, status=http_status.HTTP_201_CREATED)


class ReplyDetailView(APIView):
    """Update or delete a reply."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, reply_id):
        try:
            reply = Reply.objects.get(id=reply_id, is_deleted=False)
        except Reply.DoesNotExist:
            return Response({"error": "Reply not found"}, status=http_status.HTTP_404_NOT_FOUND)

        if reply.author != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=http_status.HTTP_403_FORBIDDEN)

        if "body" in request.data:
            reply.body = request.data["body"]
            reply.save(update_fields=["body", "updated_at"])

        serializer = ReplySerializer(reply, context={"request": request})
        return Response(serializer.data)

    def delete(self, request, reply_id):
        try:
            reply = Reply.objects.get(id=reply_id, is_deleted=False)
        except Reply.DoesNotExist:
            return Response({"error": "Reply not found"}, status=http_status.HTTP_404_NOT_FOUND)

        if reply.author != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied"}, status=http_status.HTTP_403_FORBIDDEN)

        reply.is_deleted = True
        reply.save(update_fields=["is_deleted"])

        # Update reply count
        Thread.objects.filter(id=reply.thread_id).update(reply_count=F("reply_count") - 1)

        return Response(status=http_status.HTTP_204_NO_CONTENT)


class VoteView(APIView):
    """Vote on a thread or reply."""
    permission_classes = [IsAuthenticated]

    def post(self, request, thread_id=None, reply_id=None):
        vote_type = request.data.get("vote_type", "up")
        if vote_type not in ("up", "down"):
            return Response(
                {"error": "Invalid vote type"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            if thread_id:
                return self._vote_thread(request, thread_id, vote_type)
            if reply_id:
                return self._vote_reply(request, reply_id, vote_type)
            return Response({"error": "Invalid target"}, status=http_status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Vote failed for thread=%s reply=%s: %s", thread_id, reply_id, exc)
            return Response(
                {"error": "Vote could not be recorded"},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _vote_thread(self, request, thread_id, vote_type):
        try:
            target = Thread.objects.get(id=thread_id, is_deleted=False)
        except Thread.DoesNotExist:
            return Response({"error": "Thread not found"}, status=http_status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            return self._apply_thread_vote(request, thread_id, target, vote_type)

    def _apply_thread_vote(self, request, thread_id, target, vote_type):
        existing = ThreadVote.objects.filter(user=request.user, thread=target).first()
        if existing:
            if existing.vote_type == vote_type:
                existing.delete()
                if vote_type == "up" and target.upvotes > 0:
                    Thread.objects.filter(id=thread_id).update(
                        upvotes=Greatest(F("upvotes") - 1, 0)
                    )
                return Response({"status": "vote_removed"})
            was_up = existing.vote_type == "up"
            existing.vote_type = vote_type
            existing.save(update_fields=["vote_type"])
            if was_up and vote_type == "down" and target.upvotes > 0:
                Thread.objects.filter(id=thread_id).update(
                    upvotes=Greatest(F("upvotes") - 1, 0)
                )
            elif not was_up and vote_type == "up":
                Thread.objects.filter(id=thread_id).update(upvotes=F("upvotes") + 1)
            return Response({"status": "vote_changed"})

        ThreadVote.objects.create(user=request.user, thread=target, vote_type=vote_type)
        if vote_type == "up":
            Thread.objects.filter(id=thread_id).update(upvotes=F("upvotes") + 1)
        return Response({"status": "voted"}, status=http_status.HTTP_201_CREATED)

    def _vote_reply(self, request, reply_id, vote_type):
        try:
            target = Reply.objects.get(id=reply_id, is_deleted=False)
        except Reply.DoesNotExist:
            return Response({"error": "Reply not found"}, status=http_status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            return self._apply_reply_vote(request, reply_id, target, vote_type)

    def _apply_reply_vote(self, request, reply_id, target, vote_type):
        existing = ThreadVote.objects.filter(user=request.user, reply=target).first()
        if existing:
            if existing.vote_type == vote_type:
                existing.delete()
                if vote_type == "up" and target.upvotes > 0:
                    Reply.objects.filter(id=reply_id).update(
                        upvotes=Greatest(F("upvotes") - 1, 0)
                    )
                return Response({"status": "vote_removed"})
            was_up = existing.vote_type == "up"
            existing.vote_type = vote_type
            existing.save(update_fields=["vote_type"])
            if was_up and vote_type == "down" and target.upvotes > 0:
                Reply.objects.filter(id=reply_id).update(
                    upvotes=Greatest(F("upvotes") - 1, 0)
                )
            elif not was_up and vote_type == "up":
                Reply.objects.filter(id=reply_id).update(upvotes=F("upvotes") + 1)
            return Response({"status": "vote_changed"})

        ThreadVote.objects.create(user=request.user, reply=target, vote_type=vote_type)
        if vote_type == "up":
            Reply.objects.filter(id=reply_id).update(upvotes=F("upvotes") + 1)
        return Response({"status": "voted"}, status=http_status.HTTP_201_CREATED)
