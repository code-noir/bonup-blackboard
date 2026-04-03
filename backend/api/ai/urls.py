# backend/api/ai/urls.py

from django.urls import path

from .views import AIChatView, AIConversationListView, AIConversationDetailView

urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("conversations/", AIConversationListView.as_view(), name="ai-conversations"),
    path("conversations/<uuid:conversation_id>/", AIConversationDetailView.as_view(), name="ai-conversation-detail"),
]
