
# backend/api/obligations/urls.py

from django.urls import path
from backend.api.contracts.proof_views import ObligationProofOfWorkAPIView
from .views import (
    ObligationExecutionSessionDetailAPIView,
    ObligationListAPIView,
    ObligationDetailAPIView,
    ObligationTimelineAPIView,
    ObligationNextActionsAPIView,
    ObligationDashboardSummaryAPIView,
    ObligationExecutionSessionListAPIView,
    ObligationExecutionEventListAPIView,
    ObligationApprovalRequestListAPIView,
    ObligationPromotionListAPIView,
    ObligationPromotedSideObligationListAPIView,
    ObligationExecutionSessionCloseAPIView,
    ObligationExecutionEventCreateAPIView,
    ObligationApprovalRequestApproveAPIView,
    ObligationApprovalRequestRejectAPIView,
    ObligationExecutionEventPromotionAPIView,
    ObligationValueAdjustmentListCreateAPIView,
    ObligationResolveAPIView,
    ObligationPaymentResolveAPIView,
    ObligationExecutionSessionDetailAPIView,
    ObligationExecutionEventDetailAPIView,
    ObligationExecutionEventDeleteAPIView,
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
    "execution-sessions/<uuid:session_id>/",
    ObligationExecutionSessionDetailAPIView.as_view(),
    name="obligation-execution-session-detail",
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
        "<str:obligation_type>/<uuid:obligation_id>/promotions/",
        ObligationPromotionListAPIView.as_view(),
        name="obligation-promotion-list",
    ),
      path(
    "execution-events/<uuid:event_id>/",
    ObligationExecutionEventDetailAPIView.as_view(),
    name="obligation-execution-event-detail",
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
    "<str:obligation_type>/<uuid:obligation_id>/resolve/",
    ObligationResolveAPIView.as_view(),
    name="obligation-resolve",
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

    path(
    "execution-events/<uuid:execution_event_id>/promote/",
    ObligationExecutionEventPromotionAPIView.as_view(),
    name="obligation-execution-event-promote",
    ),

    path(
    "<str:obligation_type>/<uuid:obligation_id>/value-adjustments/",
    ObligationValueAdjustmentListCreateAPIView.as_view(),
    name="obligation-value-adjustment-list",
    ),

    path(
    "payment/<uuid:obligation_id>/resolve/",
    ObligationPaymentResolveAPIView.as_view(),
    name="obligation-payment-resolve",
    ),

    path(
        "execution-events/<uuid:event_id>/delete/",
        ObligationExecutionEventDeleteAPIView.as_view(),
        name="obligation-execution-event-delete",
    ),


]


