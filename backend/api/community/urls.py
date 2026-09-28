from django.urls import path

from backend.api.community.views import (
    CommunityDetailView,
    CommunityDiscoverView,
    CommunityJoinRequestCreateView,
    CommunityJoinRequestDecisionView,
    CommunityJoinRequestListView,
    CommunityListCreateView,
    CommunityProfileView,
    FriendListCreateView,
    FriendRequestDecisionView,
    PeopleSearchView,
)


urlpatterns = [
    path("discover/", CommunityDiscoverView.as_view(), name="community-discover"),
    path("discover/<uuid:community_id>/", CommunityProfileView.as_view(), name="community-profile"),
    path("people/", PeopleSearchView.as_view(), name="community-people"),
    path("friends/", FriendListCreateView.as_view(), name="community-friends"),
    path("friends/requests/<uuid:request_id>/<str:decision>/", FriendRequestDecisionView.as_view(), name="community-friend-request-decision"),
    path("join-requests/", CommunityJoinRequestListView.as_view(), name="community-join-requests"),
    path("join-requests/<uuid:request_id>/<str:decision>/", CommunityJoinRequestDecisionView.as_view(), name="community-join-request-decision"),
    path("<uuid:community_id>/join-requests/", CommunityJoinRequestCreateView.as_view(), name="community-join-request-create"),
    path("", CommunityListCreateView.as_view(), name="community-list-create"),
    path("<uuid:community_id>/", CommunityDetailView.as_view(), name="community-detail"),
]
