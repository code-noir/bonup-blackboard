# backend/api/sol/urls.py

from django.urls import path

from .views import (
    SolContributionUpdateView,
    SolDashboardView,
    SolDetailView,
    SolListCreateView,
    SolMemberContractView,
    SolMemberDeleteView,
    SolMemberListCreateView,
    SolMembershipDetailView,
    SolMembershipListView,
    SolNotesListCreateView,
    SolPayoutDetailView,
    SolPayoutListCreateView,
    SolPayoutRearrangeView,
    SolTipCreateView,
)

urlpatterns = [
    # --------------------------------------------------
    # Member self-service  (must be before <uuid:sol_id>/)
    # --------------------------------------------------
    path("memberships/", SolMembershipListView.as_view(), name="sol-memberships"),
    path("memberships/<uuid:sol_id>/", SolMembershipDetailView.as_view(), name="sol-membership-detail"),

    # --------------------------------------------------
    # Manager: Sol CRUD
    # --------------------------------------------------
    path("", SolListCreateView.as_view(), name="sol-list-create"),
    path("<uuid:sol_id>/", SolDetailView.as_view(), name="sol-detail"),

    # --------------------------------------------------
    # Manager: Members
    # --------------------------------------------------
    path("<uuid:sol_id>/members/", SolMemberListCreateView.as_view(), name="sol-members"),
    path("<uuid:sol_id>/members/<uuid:member_id>/", SolMemberDeleteView.as_view(), name="sol-member-delete"),
    path("<uuid:sol_id>/members/<uuid:member_id>/contract/", SolMemberContractView.as_view(), name="sol-member-contract"),

    # --------------------------------------------------
    # Manager: Payouts
    # --------------------------------------------------
    path("<uuid:sol_id>/payouts/", SolPayoutListCreateView.as_view(), name="sol-payouts"),
    path("<uuid:sol_id>/payouts/<uuid:payout_id>/", SolPayoutDetailView.as_view(), name="sol-payout-detail"),
    path("<uuid:sol_id>/payouts/<uuid:payout_id>/rearrange/", SolPayoutRearrangeView.as_view(), name="sol-payout-rearrange"),
    path(
        "<uuid:sol_id>/payouts/<uuid:payout_id>/contributions/<uuid:contribution_id>/",
        SolContributionUpdateView.as_view(),
        name="sol-contribution-update",
    ),

    # --------------------------------------------------
    # Manager: Dashboard & Notes
    # --------------------------------------------------
    path("<uuid:sol_id>/dashboard/", SolDashboardView.as_view(), name="sol-dashboard"),
    path("<uuid:sol_id>/notes/", SolNotesListCreateView.as_view(), name="sol-notes"),

    # --------------------------------------------------
    # Tips (any member)
    # --------------------------------------------------
    path("<uuid:sol_id>/tips/", SolTipCreateView.as_view(), name="sol-tips"),
]
