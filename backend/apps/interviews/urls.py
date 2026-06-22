from django.urls import path

from .analytics_views import CandidateAnalyticsView, RecruiterComparisonView
from .async_video_views import (
    AsyncRoundFinalizeView,
    AsyncRoundPromptsView,
    AsyncRoundResponseView,
    AsyncRoundReviewView,
)
from .billing_views import (
    CreateInterviewRazorpayOrderView,
    CreateInterviewStripeCheckoutView,
    DemoActivateInterviewPlanView,
    VerifyInterviewRazorpayPaymentView,
)
from .gdpr_views import InterviewDeleteResumeView, InterviewExportTranscriptsView
from .invitation_views import (
    AcceptInvitationView,
    InvitationDetailView,
    InvitationListCreateView,
    PublicInvitationView,
)
from .join_views import UserPendingJoinRequestsView, UserRespondJoinRequestView
from .report_views import InterviewRoundTranscriptView
from .template_views import (
    InterviewTemplateDetailView,
    InterviewTemplateLaunchView,
    InterviewTemplateListView,
)
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

    # --- Parity features (NEW — wire into AppRouter/client) ---
    # Performance analytics: candidate dashboard + recruiter comparison.
    path("analytics/me/", CandidateAnalyticsView.as_view(), name="interview-analytics-me"),
    path("analytics/compare/", RecruiterComparisonView.as_view(), name="interview-analytics-compare"),
    # Interview templates / job-role library + question-set launch.
    path("templates/", InterviewTemplateListView.as_view(), name="interview-templates"),
    path("templates/<uuid:template_id>/", InterviewTemplateDetailView.as_view(), name="interview-template-detail"),
    path("templates/<uuid:template_id>/launch/", InterviewTemplateLaunchView.as_view(), name="interview-template-launch"),
    # Candidate invitation flow (shareable links).
    path("invitations/", InvitationListCreateView.as_view(), name="interview-invitations"),
    path("invitations/<uuid:invitation_id>/", InvitationDetailView.as_view(), name="interview-invitation-detail"),
    path("invite/<uuid:token>/", PublicInvitationView.as_view(), name="interview-invite-public"),
    path("invite/<uuid:token>/accept/", AcceptInvitationView.as_view(), name="interview-invite-accept"),
    # One-way async video interview.
    path("rounds/<uuid:round_id>/async/prompts/", AsyncRoundPromptsView.as_view(), name="interview-async-prompts"),
    path("rounds/<uuid:round_id>/async/response/", AsyncRoundResponseView.as_view(), name="interview-async-response"),
    path("rounds/<uuid:round_id>/async/finalize/", AsyncRoundFinalizeView.as_view(), name="interview-async-finalize"),
    path("rounds/<uuid:round_id>/async/review/", AsyncRoundReviewView.as_view(), name="interview-async-review"),
    # Rich transcript w/ timestamps + résumé highlights mapped to questions.
    path("rounds/<uuid:round_id>/transcript/", InterviewRoundTranscriptView.as_view(), name="interview-transcript"),
]
