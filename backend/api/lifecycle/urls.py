from django.urls import path

from .views import LifecycleAttachmentDeliveryAPIView, AgreementPerformanceListAPIView, LifecycleAgreementAPIView, LifecycleChangeProposalAPIView, LifecycleChangeProposalDecisionAPIView, LifecycleChangeProposalDetailAPIView, LifecycleChangeProposalMessageAPIView, LifecycleItemActionAPIView, LifecycleItemAttachmentAPIView, LifecycleItemCreateAPIView, LifecycleItemDetailAPIView, LifecycleItemMessageAPIView, LifecycleItemResponseAPIView, LifecycleOperationalObligationListAPIView, LifecycleReadyForPerformanceAPIView

urlpatterns = [
    path("items/<uuid:item_id>/attachments/<uuid:attachment_id>/delivery/", LifecycleAttachmentDeliveryAPIView.as_view(), name="lifecycle-attachment-delivery"),
    path("", LifecycleAgreementAPIView.as_view(), name="lifecycle-agreement"),
    path("performance/", AgreementPerformanceListAPIView.as_view(), name="agreement-performance-list"),
    path("operational-obligations/", LifecycleOperationalObligationListAPIView.as_view(), name="lifecycle-operational-obligations"),
    path("<uuid:lifecycle_id>/ready-for-performance/", LifecycleReadyForPerformanceAPIView.as_view(), name="lifecycle-ready-for-performance"),
    path("agreements/<uuid:lifecycle_id>/proposals/", LifecycleChangeProposalAPIView.as_view(), name="lifecycle-change-proposals"),
    path("proposals/<uuid:proposal_id>/", LifecycleChangeProposalDetailAPIView.as_view(), name="lifecycle-change-proposal-detail"),
    path("proposals/<uuid:proposal_id>/messages/", LifecycleChangeProposalMessageAPIView.as_view(), name="lifecycle-change-proposal-messages"),
    path("proposals/<uuid:proposal_id>/decision/", LifecycleChangeProposalDecisionAPIView.as_view(), name="lifecycle-change-proposal-decision"),
    path("<uuid:lifecycle_id>/items/", LifecycleItemCreateAPIView.as_view(), name="lifecycle-item-create"),
    path("items/<uuid:item_id>/", LifecycleItemDetailAPIView.as_view(), name="lifecycle-item-detail"),
    path("items/<uuid:item_id>/attachments/", LifecycleItemAttachmentAPIView.as_view(), name="lifecycle-item-attachments"),
    path("items/<uuid:item_id>/messages/", LifecycleItemMessageAPIView.as_view(), name="lifecycle-item-messages"),
    path("items/<uuid:item_id>/responses/", LifecycleItemResponseAPIView.as_view(), name="lifecycle-item-responses"),
    path("items/<uuid:item_id>/actions/", LifecycleItemActionAPIView.as_view(), name="lifecycle-item-action"),
]
