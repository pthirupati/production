from rest_framework import serializers
from .models import Rating


class RatingSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Rating
        fields = [
            "id", "user", "username", "rating_type", "scenario",
            "score", "review", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "username", "created_at", "updated_at"]


class RatingSummarySerializer(serializers.Serializer):
    average_score = serializers.FloatField()
    total_ratings = serializers.IntegerField()
    distribution = serializers.DictField()
