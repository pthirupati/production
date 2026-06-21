from django.urls import path

from .billing_views import (
    CreateInterviewRazorpayOrderView,
    CreateInterviewStripeCheckoutView,
    DemoActivateInterviewPlanView,
    VerifyInterviewRazorpayPaymentView,
)
from .gdpr_views import InterviewDeleteResumeView, InterviewExportTranscriptsView
from .join_views import UserPendingJoinRequestsView, UserRespondJoinRequestView
from .voice_views import InterviewVoiceConfigView
from . import tts_views, stt_views
from .views import (
    CandidateProfileView,
    CandidateResumeScoreView,
    InterviewCampaignDetailView,
    InterviewCampaignListView,
    InterviewCertificateVerifyView,
    InterviewEntitlementView,
    InterviewPlansView,
    InterviewRoundAvStatusView,
    InterviewRoundDetailView,
    InterviewRoundEndView,
    InterviewRoundExtendView,
    InterviewRoundJoinView,
    InterviewRoundMessageView,
    InterviewRoundScheduleView,
    InterviewRoundStartView,
    InterviewVoicesView,
    InterviewPracticalLabView,
    InterviewRoundPracticalValidateView,
    InterviewCertificatesListView,
    InterviewRoundIcalView,
    InterviewSampleView,
)

urlpatterns = [
    path("sample/", InterviewSampleView.as_view()),
    path("plans/", InterviewPlansView.as_view()),
    path("entitlement/", InterviewEntitlementView.as_view()),
    path("profile/", CandidateProfileView.as_view()),
    path("profile/resume-score/", CandidateResumeScoreView.as_view()),
    path("voices/", InterviewVoicesView.as_view()),
    path("campaigns/", InterviewCampaignListView.as_view()),
    path("campaigns/<uuid:campaign_id>/", InterviewCampaignDetailView.as_view()),
    path("rounds/<uuid:round_id>/", InterviewRoundDetailView.as_view()),
    path("rounds/<uuid:round_id>/schedule/", InterviewRoundScheduleView.as_view()),
    path("rounds/<uuid:round_id>/start/", InterviewRoundStartView.as_view()),
    path("rounds/<uuid:round_id>/message/", InterviewRoundMessageView.as_view()),
    path("rounds/<uuid:round_id>/av/", InterviewRoundAvStatusView.as_view()),
    path("rounds/<uuid:round_id>/extend/", InterviewRoundExtendView.as_view()),
    path("rounds/<uuid:round_id>/end/", InterviewRoundEndView.as_view()),
    path("rounds/<uuid:round_id>/practical-lab/", InterviewPracticalLabView.as_view()),
    path("rounds/<uuid:round_id>/practical-validate/", InterviewRoundPracticalValidateView.as_view()),
    path("rounds/<uuid:round_id>/ical/", InterviewRoundIcalView.as_view()),
    path("join/<uuid:invite_token>/", InterviewRoundJoinView.as_view()),
    path("certificate/verify/", InterviewCertificateVerifyView.as_view()),
    path("billing/razorpay/order/", CreateInterviewRazorpayOrderView.as_view()),
    path("billing/razorpay/verify/", VerifyInterviewRazorpayPaymentView.as_view()),
    path("billing/demo-activate/", DemoActivateInterviewPlanView.as_view()),
    path("profile/resume/", InterviewDeleteResumeView.as_view()),
    path("export/transcripts/", InterviewExportTranscriptsView.as_view()),
    path("certificates/", InterviewCertificatesListView.as_view()),
    path("billing/stripe/checkout/", CreateInterviewStripeCheckoutView.as_view()),
    path("voice/config/", InterviewVoiceConfigView.as_view()),
    path("rounds/<uuid:round_id>/join-requests/", UserPendingJoinRequestsView.as_view()),
    path("join-requests/<uuid:request_id>/respond/", UserRespondJoinRequestView.as_view()),
    # TTS/STT API endpoints (added with LLM upgrade)
    path("tts/config/", tts_views.TTSConfigView.as_view(), name="tts-config"),
    path("tts/synthesize/", tts_views.TTSSynthesizeView.as_view(), name="tts-synthesize"),
    path("stt/config/", stt_views.STTConfigView.as_view(), name="stt-config"),
    path("stt/transcribe/", stt_views.STTTranscribeView.as_view(), name="stt-transcribe"),
]
