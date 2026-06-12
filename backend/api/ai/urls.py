# backend/api/ai/urls.py

from django.urls import path

from .views import (
    AIChatView,
    AIConversationListView,
    AIConversationDetailView,
    AnalyzeContractView,
    CounterContractView,
    ImportContractView,
    GenerateContractDraftView,
)
from .workflow_views import (
    CounterDraftApproveAPIView,
    CounterpartyWorkflowActionAPIView,
    CounterpartyWorkflowDetailAPIView,
    WorkflowAdvanceAPIView,
    WorkflowCommentsListCreateAPIView,
    WorkflowDetailAPIView,
    WorkflowForContractAPIView,
    WorkflowListCreateAPIView,
    WorkflowSendAPIView,
    WorkflowShareLinkAcceptAPIView,
    WorkflowShareLinkCreateAPIView,
    WorkflowShareLinkDetailAPIView,
)

urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("conversations/", AIConversationListView.as_view(), name="ai-conversations"),
    path("conversations/<uuid:conversation_id>/", AIConversationDetailView.as_view(), name="ai-conversation-detail"),
    path("analyze-contract/", AnalyzeContractView.as_view(), name="ai-analyze-contract"),
    path("counter-contract/", CounterContractView.as_view(), name="ai-counter-contract"),
    path("import-contract/", ImportContractView.as_view(), name="ai-import-contract"),
    path("contracts/generate-draft/", GenerateContractDraftView.as_view(), name="ai-contract-generate-draft"),
    path("workflows/", WorkflowListCreateAPIView.as_view(), name="ai-workflows"),
    path("workflows/for-contract/", WorkflowForContractAPIView.as_view(), name="ai-workflow-for-contract"),
    path("workflows/<uuid:workflow_id>/", WorkflowDetailAPIView.as_view(), name="ai-workflow-detail"),
    path("workflows/<uuid:workflow_id>/advance/", WorkflowAdvanceAPIView.as_view(), name="ai-workflow-advance"),
    path("workflows/<uuid:workflow_id>/send/", WorkflowSendAPIView.as_view(), name="ai-workflow-send"),
    path("workflows/<uuid:workflow_id>/share-link/", WorkflowShareLinkCreateAPIView.as_view(), name="ai-workflow-share-link"),
    path("workflows/<uuid:workflow_id>/comments/", WorkflowCommentsListCreateAPIView.as_view(), name="ai-workflow-comments"),
    path("workflow-shares/<uuid:token>/", WorkflowShareLinkDetailAPIView.as_view(), name="ai-workflow-share-detail"),
    path("workflow-shares/<uuid:token>/accept/", WorkflowShareLinkAcceptAPIView.as_view(), name="ai-workflow-share-accept"),
    path("counterparty/workflows/<uuid:workflow_id>/", CounterpartyWorkflowDetailAPIView.as_view(), name="ai-counterparty-workflow-detail"),
    path("counterparty/workflows/<uuid:workflow_id>/<str:action>/", CounterpartyWorkflowActionAPIView.as_view(), name="ai-counterparty-workflow-action"),
    path("counter-drafts/<uuid:draft_id>/approve/", CounterDraftApproveAPIView.as_view(), name="ai-counter-draft-approve"),
]
