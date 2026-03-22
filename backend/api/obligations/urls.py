
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
    ObligationExecutionEventListAPIView,
    ObligationApprovalRequestListAPIView,
    ObligationValueAdjustmentListAPIView,
    ObligationPromotionListAPIView,
    ObligationPromotedSideObligationListAPIView,
    ObligationExecutionSessionCloseAPIView,
    ObligationExecutionEventCreateAPIView,
    ObligationApprovalRequestApproveAPIView,
    ObligationApprovalRequestRejectAPIView,


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
        "execution-sessions/<uuid:session_id>/close/",
        ObligationExecutionSessionCloseAPIView.as_view(),
        name="obligation-execution-session-close",
    ),
    path(
        "execution-sessions/<uuid:session_id>/execution-events/",
        ObligationExecutionEventCreateAPIView.as_view(),
        name="obligation-execution-event-create",
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
        "<str:obligation_type>/<uuid:obligation_id>/execution-events/",
        ObligationExecutionEventListAPIView.as_view(),
        name="obligation-execution-event-list",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/approval-requests/",
        ObligationApprovalRequestListAPIView.as_view(),
        name="obligation-approval-request-list",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/value-adjustments/",
        ObligationValueAdjustmentListAPIView.as_view(),
        name="obligation-value-adjustment-list",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/promotions/",
        ObligationPromotionListAPIView.as_view(),
        name="obligation-promotion-list",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/promoted-side-obligations/",
        ObligationPromotedSideObligationListAPIView.as_view(),
        name="obligation-promoted-side-obligation-list",
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
    path(
        "<str:obligation_type>/<uuid:obligation_id>/",
        ObligationDetailAPIView.as_view(),
        name="obligation-detail",
    ),

    path(
    "approval-requests/<uuid:approval_id>/approve/",
    ObligationApprovalRequestApproveAPIView.as_view(),
    name="obligation-approval-request-approve",
    ),
    
    path(
        "approval-requests/<uuid:approval_id>/reject/",
        ObligationApprovalRequestRejectAPIView.as_view(),
        name="obligation-approval-request-reject",
    ),

]


