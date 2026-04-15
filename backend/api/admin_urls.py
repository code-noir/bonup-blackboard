# backend/api/admin_urls.py

from django.urls import path

from .admin_views import (
    AdminActivityListView,
    AdminContractListView,
    AdminEntityListView,
    AdminSolListView,
    AdminSubscriptionListView,
    AdminSummaryView,
    AdminUserDetailView,
    AdminUserListView,
)

urlpatterns = [
    path("summary/",            AdminSummaryView.as_view(),           name="admin-summary"),
    path("users/",              AdminUserListView.as_view(),           name="admin-users"),
    path("users/<int:pk>/",     AdminUserDetailView.as_view(),         name="admin-user-detail"),
    path("subscriptions/",      AdminSubscriptionListView.as_view(),   name="admin-subscriptions"),
    path("sol/",                AdminSolListView.as_view(),            name="admin-sol"),
    path("entities/",           AdminEntityListView.as_view(),         name="admin-entities"),
    path("contracts/",          AdminContractListView.as_view(),       name="admin-contracts"),
    path("activity/",           AdminActivityListView.as_view(),       name="admin-activity"),
]
