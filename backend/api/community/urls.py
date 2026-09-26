from django.urls import path

from backend.api.community.views import CommunityDetailView, CommunityListCreateView


urlpatterns = [
    path("", CommunityListCreateView.as_view(), name="community-list-create"),
    path("<uuid:community_id>/", CommunityDetailView.as_view(), name="community-detail"),
]
