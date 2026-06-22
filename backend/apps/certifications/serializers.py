from rest_framework import serializers

from .models import CertEarnedCertificate, CertificationTrack


class TrackListSerializer(serializers.ModelSerializer):
    """Lightweight card payload for the /certifications index."""

    objective_count = serializers.IntegerField(read_only=True)
    scenario_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CertificationTrack
        fields = [
            "slug",
            "code",
            "name",
            "vendor",
            "description",
            "exam_duration_minutes",
            "passing_score",
            "objective_count",
            "scenario_count",
        ]


class CertificateSerializer(serializers.ModelSerializer):
    track_code = serializers.CharField(source="track.code", read_only=True)
    track_name = serializers.CharField(source="track.name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = CertEarnedCertificate
        fields = [
            "certificate_id",
            "track_code",
            "track_name",
            "holder_name",
            "score",
            "issued_at",
            "expires_at",
            "is_expired",
        ]
