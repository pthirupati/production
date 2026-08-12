from django.urls import path
from .views import (
    PlatformConfigView,
    ActiveCampaignsView,
    TechnologiesListView,
    TechnologyDetailView,
    ScenariosListView,
    ScenarioDetailView,
    CategoriesListView,
    TagsListView,
    BookmarkView,
    StartLabView,
    StopLabView,
    RestartLabView,
    ValidateLabView,
    ValidateGuidedStepView,
    CodingSpecView,
    CodeValidateView,
    IdeDraftView,
    ApiClientDraftView,
    ApiClientSendView,
    CodeMentorView,
    PromptValidateView,
    ActiveLabsView,
    LabSessionStatusView,
    LabHintsView,
    LabAiHintView,
    UserProgressView,
    UserAchievementsView,
    LeaderboardView,
    PlatformStatsView,
    UserPlanView,
    CommandHistoryView,
    SessionReplayView,
    ExpiredSessionSolutionView,
    AchievementsCertificateView,
    CertificateVerifyView,
    BlogListView,
    BlogDetailView,
    ProjectsListView,
    ProjectDetailView,
    ProjectStartView,
    ProjectTaskUpdateView,
    ProjectJiraBotView,
    ExtendLabView,
    LabAiReviewView,
)
from .engagement import (
    DailyChallengeView,
    StreakView,
    XpView,
    ScenarioStatsView,
)

urlpatterns = [
    # Platform configuration
    path("config/", PlatformConfigView.as_view()),
    path("campaigns/active/", ActiveCampaignsView.as_view()),

    # Public catalog
    path("technologies/", TechnologiesListView.as_view()),
    path("technologies/<slug:slug>/", TechnologyDetailView.as_view()),
    path("scenarios/", ScenariosListView.as_view()),
    path("scenarios/<slug:slug>/stats/", ScenarioStatsView.as_view()),
    path("scenarios/<slug:slug>/", ScenarioDetailView.as_view()),
    path("categories/", CategoriesListView.as_view()),
    path("tags/", TagsListView.as_view()),
    path("stats/", PlatformStatsView.as_view()),

    # Bookmarks
    path("bookmarks/", BookmarkView.as_view()),

    # Labs
    path("labs/<int:scenario_id>/start/", StartLabView.as_view()),
    path("labs/<uuid:session_id>/stop/", StopLabView.as_view()),
    path("labs/<uuid:session_id>/restart/", RestartLabView.as_view(), name="lab-restart"),
    path("labs/<uuid:session_id>/validate/", ValidateLabView.as_view()),
    path("labs/<uuid:session_id>/guided-step/", ValidateGuidedStepView.as_view()),
    path("labs/<uuid:session_id>/coding-spec/", CodingSpecView.as_view()),
    path("labs/<uuid:session_id>/ide-draft/", IdeDraftView.as_view()),
    path("labs/<uuid:session_id>/api-client/draft/", ApiClientDraftView.as_view()),
    path("labs/<uuid:session_id>/api-client/send/", ApiClientSendView.as_view()),
    path("labs/<uuid:session_id>/code-validate/", CodeValidateView.as_view()),
    path("labs/<uuid:session_id>/mentor/", CodeMentorView.as_view()),
    path("labs/<uuid:session_id>/prompt-validate/", PromptValidateView.as_view()),
    path("labs/<uuid:session_id>/hints/", LabHintsView.as_view()),
    path("labs/<uuid:session_id>/ai-hint/", LabAiHintView.as_view()),
    path("labs/<uuid:session_id>/commands/", CommandHistoryView.as_view()),
    path("labs/<uuid:session_id>/replay/", SessionReplayView.as_view()),
    path("labs/<uuid:session_id>/solution/", ExpiredSessionSolutionView.as_view()),
    path("labs/<uuid:session_id>/status/", LabSessionStatusView.as_view()),
    path("labs/<uuid:session_id>/extend/", ExtendLabView.as_view()),
    path("labs/<uuid:session_id>/ai-review/", LabAiReviewView.as_view()),
    path("labs/active/", ActiveLabsView.as_view()),

    # User
    path("progress/", UserProgressView.as_view()),
    path("achievements/", UserAchievementsView.as_view()),
    path("achievements/certificate/", AchievementsCertificateView.as_view()),
    path("achievements/certificate/verify/", CertificateVerifyView.as_view()),
    path("leaderboard/", LeaderboardView.as_view()),

    # Engagement loop (daily challenge, streak calendar, XP/levels)
    path("daily-challenge/", DailyChallengeView.as_view()),
    path("streak/", StreakView.as_view()),
    path("xp/", XpView.as_view()),

    # Plan
    path("plan/", UserPlanView.as_view()),

    # Blog CMS (public)
    path("blog/", BlogListView.as_view()),
    path("blog/<slug:slug>/", BlogDetailView.as_view()),

    # Projects (catalog index + detail before id-scoped actions — audit §C3)
    path("projects/", ProjectsListView.as_view()),
    path("projects/<slug:slug>/", ProjectDetailView.as_view()),
    path("projects/<int:project_id>/start/", ProjectStartView.as_view()),
    path("projects/<int:project_id>/tasks/<int:task_id>/update/", ProjectTaskUpdateView.as_view()),
    path("projects/<int:project_id>/tasks/<int:task_id>/bot/", ProjectJiraBotView.as_view()),
]
