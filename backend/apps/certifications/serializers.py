from rest_framework import serializers

from .models import CertEarnedCertificate, CertificationTrack


class AdminTrackSerializer(serializers.ModelSerializer):
    """Full read/write payload for the admin certification-management page.

    Mirrors how ``adminpanel`` exposes ``Technology`` — the admin can toggle
    active/maintenance/free, set pricing, and tune the exam settings. Slug/code
    are read-only here so admins manage existing seeded tracks (created via the
    seed command / Django admin) rather than minting new vendor codes by hand.
    """

    objective_count = serializers.IntegerField(read_only=True)
    scenario_count = serializers.IntegerField(read_only=True)
    technology_name = serializers.CharField(source="technology.name", read_only=True)
    technology_slug = serializers.CharField(source="technology.slug", read_only=True)
    technology_price = serializers.IntegerField(source="technology.price", read_only=True)

    class Meta:
        model = CertificationTrack
        fields = [
            "id",
            "slug",
            "code",
            "name",
            "vendor",
            "description",
            "technology_name",
            "technology_slug",
            "technology_price",
            "exam_duration_minutes",
            "passing_score",
            "validity_months",
            "price",
            "addon_price",
            "is_free",
            "coming_soon",
            "is_active",
            "maintenance_enabled",
            "maintenance_message",
            "maintenance_scheduled_start",
            "maintenance_scheduled_end",
            "order",
            "objective_count",
            "scenario_count",
        ]
        read_only_fields = ["id", "slug", "code"]


class TrackListSerializer(serializers.ModelSerializer):
    """Lightweight card payload for the /certifications index."""

    objective_count = serializers.IntegerField(read_only=True)
    scenario_count = serializers.IntegerField(read_only=True)
    technology_slug = serializers.CharField(source="technology.slug", read_only=True, allow_null=True)

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
            "price",
            "addon_price",
            "is_free",
            "technology_slug",
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
