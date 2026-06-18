"""Interview Studio REST API."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.models import (
    CandidateProfile,
    InterviewCampaign,
    InterviewCertificate,
    InterviewPlanTier,
    InterviewRound,
)
from apps.interviews.serializers import (
    CandidateProfileSerializer,
    InterviewCampaignDetailSerializer,
    InterviewCampaignListSerializer,
    InterviewCertificateSerializer,
    InterviewMessageSerializer,
    InterviewPlanTierSerializer,
    InterviewReportSerializer,
    InterviewRoundSerializer,
)
from apps.interviews.services.campaign_builder import create_campaign_rounds
from apps.interviews.services.entitlements import (
    consume_interview_credit,
    get_entitlement_payload,
    user_has_interview_access,
)
from apps.interviews.services import engine
from apps.interviews.services.resume_parser import extract_text_from_upload, parse_resume_text, build_profile_from_inputs
from common.throttles import InterviewRateThrottle, StrictAnonRateThrottle


class InterviewPlansView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        tiers = InterviewPlanTier.objects.filter(is_active=True)
        return Response({"plans": InterviewPlanTierSerializer(tiers, many=True).data})


class InterviewEntitlementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_entitlement_payload(request.user))


class CandidateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        return Response(CandidateProfileSerializer(profile).data)

    def put(self, request):
        import json

        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        data = request.data.copy()
        if data.get("primary_technology") in ("", "null", "undefined"):
            data["primary_technology"] = None
        elif data.get("primary_technology") is not None:
            try:
                data["primary_technology"] = int(data["primary_technology"])
            except (TypeError, ValueError):
                data["primary_technology"] = None
        for empty_field in ("current_package_lpa", "notice_period_days", "years_experience"):
            if data.get(empty_field) in ("", "null", "undefined", None):
                data[empty_field] = None
        if data.get("current_package_lpa") is not None:
            try:
                data["current_package_lpa"] = str(data["current_package_lpa"]).strip() or None
            except (TypeError, ValueError):
                data["current_package_lpa"] = None
        if data.get("notice_period_days") is not None:
            try:
                data["notice_period_days"] = int(data["notice_period_days"])
            except (TypeError, ValueError):
                data["notice_period_days"] = None
        if data.get("years_experience") is not None:
            try:
                data["years_experience"] = int(data["years_experience"])
            except (TypeError, ValueError):
                data["years_experience"] = 0

        def _coerce_json_field(raw, *, expect_list: bool):
            default = [] if expect_list else {}
            if raw is None or raw == "":
                return default
            if expect_list and isinstance(raw, list):
                return raw
            if not expect_list and isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                raw = raw.strip()
                if not raw:
                    return default
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    if expect_list and "," in raw:
                        return [p.strip() for p in raw.split(",") if p.strip()]
                    return default
                if expect_list:
                    if isinstance(parsed, list):
                        return parsed
                    if isinstance(parsed, str) and parsed.strip():
                        return [parsed.strip()]
                    return default
                if isinstance(parsed, dict):
                    return parsed
                return default
            if expect_list:
                return [str(raw).strip()] if str(raw).strip() else default
            return default

        for json_field, expect_list in (
            ("secondary_technologies", True),
            ("target_companies", True),
            ("resume_parsed", False),
        ):
            if json_field in data:
                data[json_field] = _coerce_json_field(data.get(json_field), expect_list=expect_list)
        if request.FILES.get("resume"):
            profile.resume_file = request.FILES["resume"]
            text = extract_text_from_upload(request.FILES["resume"])
            profile.resume_text = text
            profile.resume_parsed = parse_resume_text(text)
        ser = CandidateProfileSerializer(profile, data=data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        if profile.resume_file and not profile.resume_parsed:
            profile.resume_parsed = parse_resume_text(profile.resume_text)
            profile.save(update_fields=["resume_parsed"])
        elif not profile.resume_file and not (profile.resume_parsed or {}).get("has_resume"):
            tech_name = ""
            if profile.primary_technology_id:
                tech_name = getattr(profile.primary_technology, "name", "") or ""
            profile.resume_parsed = build_profile_from_inputs(
                target_role=profile.target_role,
                experience_level=profile.experience_level,
                years_experience=profile.years_experience,
                current_company=profile.current_company,
                secondary_technologies=profile.secondary_technologies or [],
                primary_technology_name=tech_name,
            )
            profile.save(update_fields=["resume_parsed"])
        return Response(CandidateProfileSerializer(profile).data)


class InterviewSampleView(APIView):
    """POST — create or resume the one-time free sample interview."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.interviews.services.sample_interview import get_or_resume_sample_campaign, sample_available_for_user

        existing = get_or_resume_sample_campaign(request.user)
        return Response({
            "sample_available": sample_available_for_user(request.user),
            "sample_interview_used": get_entitlement_payload(request.user).get("sample_interview_used"),
            "sample_duration_minutes": get_entitlement_payload(request.user).get("sample_duration_minutes", 10),
            "active_sample_campaign_id": str(existing.id) if existing else None,
            "instructions": SAMPLE_INSTRUCTIONS,
        })

    def post(self, request):
        from apps.interviews.services.sample_interview import create_sample_campaign, sample_available_for_user

        if not sample_available_for_user(request.user):
            ent = get_entitlement_payload(request.user)
            if ent.get("sample_interview_used"):
                return Response(
                    {"error": "Free sample already used. Subscribe for full interviews.", "code": "SAMPLE_USED"},
                    status=403,
                )
            return Response({"error": "Sample not available", "code": "SAMPLE_UNAVAILABLE"}, status=403)

        try:
            campaign = create_sample_campaign(request.user)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        return Response(
            InterviewCampaignDetailSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )


SAMPLE_INSTRUCTIONS = [
    "Find a quiet place with stable internet — treat it like a real video call.",
    "Allow microphone and camera when prompted; both must stay on during the session.",
    "You have about 10 minutes for 3–4 quick technical questions.",
    "Answer by voice (mic button) or type in the answer box — same as a paid interview.",
    "At the end you get mini feedback and scores; subscribe for full 3–5 round cycles and certificates.",
]


class InterviewCampaignListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = InterviewCampaign.objects.filter(user=request.user, is_archived=False).select_related("primary_technology")
        return Response({"campaigns": InterviewCampaignListSerializer(qs, many=True).data})

    def post(self, request):
        if not user_has_interview_access(request.user):
            return Response(
                {"error": "Interview subscription required", "code": "SUBSCRIPTION_REQUIRED"},
                status=403,
            )
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        round_count = int(request.data.get("round_count", 3))
        round_count = max(3, min(5, round_count))

        tier = InterviewPlanTier.objects.filter(code="pro", is_active=True).first()
        max_rounds = tier.max_rounds if tier else 5
        if round_count > max_rounds and not request.user.is_staff:
            round_count = max_rounds

        if not consume_interview_credit(request.user):
            return Response({"error": "No interview credits remaining this period"}, status=403)

        snap = CandidateProfileSerializer(profile).data
        title = request.data.get("title") or f"{profile.target_role or 'Mock Interview'} — {profile.experience_level}"

        campaign = InterviewCampaign.objects.create(
            user=request.user,
            title=title,
            round_count=round_count,
            status="scheduled",
            profile_snapshot=snap,
            primary_technology=profile.primary_technology,
            experience_level=profile.experience_level,
            plan_tier=tier,
        )
        create_campaign_rounds(campaign)
        return Response(
            InterviewCampaignDetailSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )


class InterviewCampaignDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        campaign = get_object_or_404(
            InterviewCampaign.objects.prefetch_related("rounds__messages", "rounds__report"),
            id=campaign_id,
            user=request.user,
        )
        return Response(InterviewCampaignDetailSerializer(campaign).data)

    def delete(self, request, campaign_id):
        campaign = get_object_or_404(InterviewCampaign, id=campaign_id, user=request.user)
        # Archive finished interviews (remove from history view)
        if campaign.status in ("completed", "failed", "cancelled"):
            campaign.is_archived = True
            campaign.save(update_fields=["is_archived", "updated_at"])
            return Response({"status": "archived", "id": str(campaign.id)})
        # Cancel active/scheduled interviews
        if campaign.status in ("in_progress", "scheduled"):
            return Response({"error": "Cannot delete an ongoing or scheduled interview"}, status=400)
        # Draft campaigns: archive without sending a cancellation email
        if campaign.status == "draft":
            campaign.is_archived = True
            campaign.save(update_fields=["is_archived", "updated_at"])
            return Response({"status": "archived", "id": str(campaign.id)})
        campaign.status = "cancelled"
        campaign.save(update_fields=["status", "updated_at"])
        campaign.rounds.exclude(status__in=("passed", "completed")).update(status="abandoned")
        try:
            from apps.notifications.tasks import send_notification_email
            send_notification_email.delay(
                subject=f"Interview cancelled — {campaign.title}",
                to_email=request.user.email,
                template="emails/interview_cancelled.html",
                context={"campaign_title": campaign.title, "frontend_url": settings.FRONTEND_URL},
            )
        except Exception:
            pass
        return Response({"status": "cancelled", "id": str(campaign.id)})


class InterviewRoundScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        if round_obj.status not in ("schedulable", "scheduled", "ready"):
            return Response({"error": f"Round cannot be scheduled (status={round_obj.status})"}, status=400)

        scheduled_at = request.data.get("scheduled_at")
        if scheduled_at:
            from django.utils.dateparse import parse_datetime

            dt = parse_datetime(scheduled_at)
            if dt:
                round_obj.scheduled_at = dt
        else:
            round_obj.scheduled_at = timezone.now() + timedelta(hours=1)

        if round_obj.schedule_deadline and round_obj.scheduled_at > round_obj.schedule_deadline:
            return Response({"error": "Schedule within 48 hours of previous round pass"}, status=400)

        round_obj.status = "scheduled"
        round_obj.save(update_fields=["scheduled_at", "status"])

        try:
            from apps.interviews.services.notify import notify_round_scheduled
            notify_round_scheduled(round_obj)
        except Exception:
            pass

        try:
            from apps.notifications.tasks import send_notification_email

            send_notification_email.delay(
                subject=f"FixitLab interview scheduled — {round_obj.title}",
                to_email=request.user.email,
                template="emails/interview_invite.html",
                context={
                    "round_title": round_obj.title,
                    "persona": round_obj.persona_name,
                    "scheduled_at": round_obj.scheduled_at.strftime("%B %d, %Y %H:%M UTC"),
                    "join_url": f"{settings.FRONTEND_URL}/interviews/room/{round_obj.id}",
                    "duration": round_obj.duration_minutes,
                },
            )
            round_obj.invite_email_sent = True
            round_obj.save(update_fields=["invite_email_sent"])
        except Exception:
            pass

        return Response(InterviewRoundSerializer(round_obj).data)


class InterviewRoundStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [InterviewRateThrottle]

    def post(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )

        if not (request.user.is_staff or request.user.is_superuser):
            # Platform maintenance check
            try:
                from apps.adminpanel.platform_config import is_maintenance_active
                if is_maintenance_active():
                    from apps.adminpanel.models import PlatformSettings
                    row = PlatformSettings.objects.filter(pk=1).first()
                    msg = (row.maintenance_message if row else None) or "FixitLab is currently under maintenance. Interviews are temporarily unavailable."
                    return Response({"error": "maintenance", "message": msg}, status=503)
            except Exception:
                pass
            # Interview-specific maintenance check
            try:
                from apps.interviews.models import InterviewPlatformSettings
                isettings = InterviewPlatformSettings.objects.filter(pk=1).first()
                if isettings and isettings.maintenance_enabled:
                    msg = isettings.maintenance_message or "Interview Studio is currently under maintenance."
                    return Response({"error": "interview_maintenance", "message": msg}, status=503)
            except Exception:
                pass

        if round_obj.status not in ("scheduled", "ready", "schedulable"):
            return Response({"error": "Round not ready to start"}, status=400)

        result = engine.start_round(round_obj)
        first_q = engine.ask_next_question(round_obj)
        payload = InterviewRoundSerializer(round_obj).data
        payload["intro"] = InterviewMessageSerializer(result["message"]).data
        if first_q:
            payload["first_question"] = InterviewMessageSerializer(first_q).data
        return Response(payload)


class InterviewRoundMessageView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [InterviewRateThrottle]

    def post(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        if round_obj.status != "in_progress":
            return Response({"error": "Round not in progress"}, status=400)

        answer = request.data.get("answer", "")
        meta = {
            "input_type": request.data.get("input_type", "text"),
            "command_validated": request.data.get("command_validated", False),
        }
        result = engine.submit_answer(round_obj, answer, meta)
        return Response({
            "candidate_message": InterviewMessageSerializer(result["candidate_message"]).data,
            "interviewer_reply": InterviewMessageSerializer(result["interviewer_reply"]).data,
            "score": result["score"],
            "next_question": InterviewMessageSerializer(result["next_question"]).data
            if result.get("next_question")
            else None,
        })


class InterviewRoundAvStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        mic_on = bool(request.data.get("mic_on"))
        camera_on = bool(request.data.get("camera_on"))
        result = engine.record_av_status(round_obj, mic_on, camera_on)
        if result.get("report") or result.get("action") == "end":
            return Response({
                "ended": True,
                "report": InterviewReportSerializer(result["report"]).data,
            })
        return Response(result)


class InterviewRoundExtendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        minutes = int(request.data.get("minutes", 10))
        ok = engine.extend_round(round_obj, minutes)
        if not ok:
            return Response({"error": "Extension limit reached"}, status=400)
        return Response(InterviewRoundSerializer(round_obj).data)


class InterviewRoundEndView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        reason = request.data.get("reason", "completed")
        result = engine.end_round(round_obj, reason=reason)
        data = {
            "passed": result["passed"],
            "reason": result.get("reason"),
            "report": InterviewReportSerializer(result["report"]).data,
        }
        if result.get("next_round"):
            data["next_round"] = InterviewRoundSerializer(result["next_round"]).data
        return Response(data)


class InterviewRoundDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.prefetch_related("messages", "report").select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        return Response(InterviewRoundSerializer(round_obj).data)


class InterviewRoundJoinView(APIView):
    """Join via email invite token (same user must own campaign)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, invite_token):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            invite_token=invite_token,
            campaign__user=request.user,
        )
        return Response(InterviewRoundSerializer(round_obj).data)


class InterviewCertificateVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        cert_id = request.query_params.get("certificate_id", "").strip()
        if not cert_id:
            return Response({"error": "certificate_id required"}, status=400)
        cert = InterviewCertificate.objects.filter(certificate_id=cert_id).select_related("user", "campaign").first()
        if not cert:
            return Response({"valid": False, "error": "Certificate not found"})
        if cert.expires_at < timezone.now():
            return Response({"valid": False, "error": "Certificate expired", "certificate_id": cert_id})
        return Response({
            "valid": True,
            "type": "interview",
            **InterviewCertificateSerializer(cert).data,
        })


class InterviewVoicesView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request):
        from apps.interviews.services.voice_service import voice_config_payload
        payload = voice_config_payload()
        return Response({
            "voices": payload.get("voices", []),
            "default_voice_code": payload.get("default_voice_code"),
        })


class InterviewPracticalLabView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, round_id):
        from apps.interviews.services.practical_lab import start_practical_lab

        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        if round_obj.status != "in_progress":
            return Response({"error": "Round must be in progress"}, status=400)
        result = start_practical_lab(request.user, round_obj)
        if result.get("error"):
            return Response(result, status=400)
        return Response(result)


class InterviewCertificatesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        certs = InterviewCertificate.objects.filter(user=request.user).order_by("-issued_at")
        return Response({
            "certificates": [
                {
                    "certificate_id": c.certificate_id,
                    "holder_name": c.holder_name,
                    "technology_name": c.technology_name,
                    "level": c.level,
                    "rounds_cleared": c.rounds_cleared,
                    "overall_score": c.overall_score,
                    "issued_at": c.issued_at.isoformat(),
                    "expires_at": c.expires_at.isoformat(),
                    "linkedin_share_text": c.linkedin_share_text,
                    "verify_url": f"/verify-certificate?certificate_id={c.certificate_id}",
                }
                for c in certs
            ]
        })


class InterviewRoundIcalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, round_id):
        from django.http import HttpResponse

        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        if not round_obj.scheduled_at:
            return Response({"error": "Round not scheduled"}, status=400)
        start = round_obj.scheduled_at.strftime("%Y%m%dT%H%M%SZ")
        end = (round_obj.scheduled_at + timedelta(minutes=round_obj.duration_minutes)).strftime("%Y%m%dT%H%M%SZ")
        uid = f"interview-{round_obj.id}@fixitlab"
        body = "\r\n".join([
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//FixitLab//Interview Studio//EN",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:FixitLab Interview — {round_obj.title}",
            f"DESCRIPTION:Mock interview round with {round_obj.persona_name}. Camera and mic required.",
            "END:VEVENT",
            "END:VCALENDAR",
        ])
        response = HttpResponse(body, content_type="text/calendar")
        response["Content-Disposition"] = f'attachment; filename="interview-round-{round_obj.round_number}.ics"'
        return response
