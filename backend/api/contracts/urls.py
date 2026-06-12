from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .management_views import ContractManagementSummaryAPIView
from backend.api.activity.views import ContractActivityAPIView
from backend.api.sessions.views import ContractSessionListAPIView

from .promotion_views import ExecutionEventPromotionAPIView

from .value_adjustment_views import ObligationValueAdjustmentListCreateAPIView

from .resolve_views import ( ObligationResolveAPIView, ContractPaymentResolveAPIView, )
from .views import ContractViewSet
from .version_views import (
    ContractVersionCreateAPIView,
    ContractVersionSignAPIView,
    ContractVersionRejectAPIView,
)
from .draft_views import ContractDraftAutosaveAPIView
from .prepare_views import ContractPrepareAPIView
from .invite_views import ContractInviteAPIView
from .role_switch_views import (
    ContractRoleSwitchRequestAPIView,
    ContractRoleSwitchConfirmAPIView,
)
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
from .document_views import (
    ContractDocumentListCreateAPIView,
    ContractDocumentDeleteAPIView,
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
    path(
        "<uuid:contract_id>/activity/",
        ContractActivityAPIView.as_view(),
        name="contract-activity",
    ),
    path(
        "<uuid:contract_id>/sessions/",
        ContractSessionListAPIView.as_view(),
        name="contract-sessions",
    ),
    path(
        "<uuid:contract_id>/documents/",
        ContractDocumentListCreateAPIView.as_view(),
        name="contract-documents",
    ),
    path(
        "<uuid:contract_id>/documents/<uuid:doc_id>/",
        ContractDocumentDeleteAPIView.as_view(),
        name="contract-document-delete",
    ),
    path(
        "<uuid:contract_id>/invite/",
        ContractInviteAPIView.as_view(),
        name="contract-invite",
    ),

    # --------------------------------------------------
    # Version negotiation
    # --------------------------------------------------
    path(
        "<uuid:contract_id>/prepare/",
        ContractPrepareAPIView.as_view(),
        name="contract-prepare",
    ),
    path(
        "<uuid:contract_id>/versions/",
        ContractVersionCreateAPIView.as_view(),
        name="contract-version-create",
    ),
    path(
        "<uuid:contract_id>/draft/",
        ContractDraftAutosaveAPIView.as_view(),
        name="contract-draft-autosave",
    ),
    path(
        "<uuid:contract_id>/versions/<uuid:version_id>/sign/",
        ContractVersionSignAPIView.as_view(),
        name="contract-version-sign",
    ),
    path(
        "<uuid:contract_id>/versions/<uuid:version_id>/reject/",
        ContractVersionRejectAPIView.as_view(),
        name="contract-version-reject",
    ),

    # --------------------------------------------------
    # Role switch
    # --------------------------------------------------
    path(
        "<uuid:contract_id>/request-role-switch/",
        ContractRoleSwitchRequestAPIView.as_view(),
        name="contract-request-role-switch",
    ),
    path(
        "<uuid:contract_id>/confirm-role-switch/",
        ContractRoleSwitchConfirmAPIView.as_view(),
        name="contract-confirm-role-switch",
    ),

    path("", include(router.urls)),
]
