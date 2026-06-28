from django.urls import path

from .views import AgreementPerformanceListAPIView, LifecycleAgreementAPIView, LifecycleItemActionAPIView, LifecycleItemAttachmentAPIView, LifecycleItemCreateAPIView, LifecycleItemDetailAPIView, LifecycleItemMessageAPIView, LifecycleItemResponseAPIView, LifecycleReadyForPerformanceAPIView

urlpatterns = [
    path("", LifecycleAgreementAPIView.as_view(), name="lifecycle-agreement"),
    path("performance/", AgreementPerformanceListAPIView.as_view(), name="agreement-performance-list"),
    path("<uuid:lifecycle_id>/ready-for-performance/", LifecycleReadyForPerformanceAPIView.as_view(), name="lifecycle-ready-for-performance"),
    path("<uuid:lifecycle_id>/items/", LifecycleItemCreateAPIView.as_view(), name="lifecycle-item-create"),
    path("items/<uuid:item_id>/", LifecycleItemDetailAPIView.as_view(), name="lifecycle-item-detail"),
    path("items/<uuid:item_id>/attachments/", LifecycleItemAttachmentAPIView.as_view(), name="lifecycle-item-attachments"),
    path("items/<uuid:item_id>/messages/", LifecycleItemMessageAPIView.as_view(), name="lifecycle-item-messages"),
    path("items/<uuid:item_id>/responses/", LifecycleItemResponseAPIView.as_view(), name="lifecycle-item-responses"),
    path("items/<uuid:item_id>/actions/", LifecycleItemActionAPIView.as_view(), name="lifecycle-item-action"),
]
