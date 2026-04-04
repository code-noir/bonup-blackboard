# backend/api/ai/urls.py

from django.urls import path

from .views import (
    AIChatView,
    AIConversationListView,
    AIConversationDetailView,
    AnalyzeContractView,
    CounterContractView,
    ImportContractView,
)

urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("conversations/", AIConversationListView.as_view(), name="ai-conversations"),
    path("conversations/<uuid:conversation_id>/", AIConversationDetailView.as_view(), name="ai-conversation-detail"),
    path("analyze-contract/", AnalyzeContractView.as_view(), name="ai-analyze-contract"),
    path("counter-contract/", CounterContractView.as_view(), name="ai-counter-contract"),
    path("import-contract/", ImportContractView.as_view(), name="ai-import-contract"),
]
