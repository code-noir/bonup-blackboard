
# backend/api/obligations/urls.py

from django.urls import path
from backend.api.contracts.proof_views import ObligationProofOfWorkAPIView
from .views import (
    ObligationListAPIView,
    ObligationDetailAPIView,
    ObligationTimelineAPIView,
    ObligationNextActionsAPIView,
    ObligationDashboardSummaryAPIView,
    ObligationExecutionSessionListAPIView,
)

urlpatterns = [
    path(
        "",
        ObligationListAPIView.as_view(),
        name="obligation-list",
    ),
    path(
        "dashboard-summary/",
        ObligationDashboardSummaryAPIView.as_view(),
        name="obligation-dashboard-summary",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/proof/",
        ObligationProofOfWorkAPIView.as_view(),
        name="obligation-proof-of-work",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/execution-sessions/",
        ObligationExecutionSessionListAPIView.as_view(),
        name="obligation-execution-session-list",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/",
        ObligationDetailAPIView.as_view(),
        name="obligation-detail",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/timeline/",
        ObligationTimelineAPIView.as_view(),
        name="obligation-timeline",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/next-actions/",
        ObligationNextActionsAPIView.as_view(),
        name="obligation-next-actions",
    ),
]
