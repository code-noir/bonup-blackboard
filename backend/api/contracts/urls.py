# backend/api/contracts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .management_views import ContractManagementSummaryAPIView

from .promotion_views import ExecutionEventPromotionAPIView

from .value_adjustment_views import ObligationValueAdjustmentListCreateAPIView

from .resolve_views import ( ObligationResolveAPIView, ContractPaymentResolveAPIView, )
from .views import ContractViewSet
from .obligations_views import ContractObligationsAPIView
from .proof_views import ObligationProofOfWorkAPIView

from .execution_views import (
    ObligationExecutionSessionListCreateAPIView,
    ExecutionItemCreateAPIView,
    ExecutionSessionEventListAPIView,
    ExecutionSessionCloseAPIView,
    ExecutionSessionDetailAPIView,
    ExecutionEventDetailAPIView,
    ExecutionEventDeleteAPIView,
)
from .approval_views import (
    ObligationApprovalRequestListCreateAPIView,
    ApprovalRequestApproveAPIView,
    ApprovalRequestRejectAPIView,
)

router = DefaultRouter()
router.register(r"", ContractViewSet, basename="contract")

urlpatterns = [
    path(
        "<uuid:contract_id>/obligations/",
        ContractObligationsAPIView.as_view(),
        name="contract-obligations",
    ),
    path(
        "obligations/<str:obligation_type>/<uuid:obligation_id>/proof/",
        ObligationProofOfWorkAPIView.as_view(),
        name="contract-obligation-proof-of-work",
    ),
    path(
        "obligations/<str:obligation_type>/<uuid:obligation_id>/execution-sessions/",
        ObligationExecutionSessionListCreateAPIView.as_view(),
        name="contract-obligation-execution-sessions",
    ),
    path(
        "obligations/<str:obligation_type>/<uuid:obligation_id>/approval-requests/",
        ObligationApprovalRequestListCreateAPIView.as_view(),
        name="contract-obligation-approval-requests",
    ),
    path(
        "obligations/<str:obligation_type>/<uuid:obligation_id>/value-adjustments/",
        ObligationValueAdjustmentListCreateAPIView.as_view(),
        name="contract-obligation-value-adjustments",
    ),
    path(
        "obligations/payment/<uuid:obligation_id>/resolve/",
        ContractPaymentResolveAPIView.as_view(),
        name="contract-payment-resolve",
    ),
    path(
        "obligations/<str:obligation_type>/<uuid:obligation_id>/resolve/",
        ObligationResolveAPIView.as_view(),
        name="contract-obligation-resolve",
    ),
    path(
        "execution-sessions/<uuid:session_id>/",
        ExecutionSessionDetailAPIView.as_view(),
        name="contract-execution-session-detail",
    ),
    path(
        "execution-sessions/<uuid:session_id>/execution-items/",
        ExecutionItemCreateAPIView.as_view(),
        name="contract-execution-item-create",
    ),
    path(
        "execution-sessions/<uuid:session_id>/events/",
        ExecutionSessionEventListAPIView.as_view(),
        name="contract-execution-session-events",
    ),
    path(
        "execution-sessions/<uuid:session_id>/close/",
        ExecutionSessionCloseAPIView.as_view(),
        name="contract-execution-session-close",
    ),
    path(
        "execution-events/<uuid:event_id>/",
        ExecutionEventDetailAPIView.as_view(),
        name="contract-execution-event-detail",
    ),
    path(
        "execution-events/<uuid:event_id>/delete/",
        ExecutionEventDeleteAPIView.as_view(),
        name="contract-execution-event-delete",
    ),
    path(
        "execution-events/<uuid:execution_event_id>/promote/",
        ExecutionEventPromotionAPIView.as_view(),
        name="contract-execution-event-promote",
    ),
    path(
        "approval-requests/<uuid:approval_id>/approve/",
        ApprovalRequestApproveAPIView.as_view(),
        name="contract-approval-request-approve",
    ),
    path(
        "approval-requests/<uuid:approval_id>/reject/",
        ApprovalRequestRejectAPIView.as_view(),
        name="contract-approval-request-reject",
    ),
    path(
        "<uuid:contract_id>/management-summary/",
        ContractManagementSummaryAPIView.as_view(),
        name="contract-management-summary",
    ),
    path("", include(router.urls)),
]