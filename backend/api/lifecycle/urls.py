from django.urls import path

from .views import LifecycleAgreementAPIView, LifecycleItemCreateAPIView, LifecycleItemDetailAPIView

urlpatterns = [
    path("", LifecycleAgreementAPIView.as_view(), name="lifecycle-agreement"),
    path("<uuid:lifecycle_id>/items/", LifecycleItemCreateAPIView.as_view(), name="lifecycle-item-create"),
    path("items/<uuid:item_id>/", LifecycleItemDetailAPIView.as_view(), name="lifecycle-item-detail"),
]
