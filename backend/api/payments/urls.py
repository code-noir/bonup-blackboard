from django.urls import path
from .views import PaymentListCreateAPIView, PaymentDetailAPIView

urlpatterns = [
    path(
        "",
        PaymentListCreateAPIView.as_view(),
        name="payment-list-create",
    ),
    path(
        "<uuid:payment_id>/",
        PaymentDetailAPIView.as_view(),
        name="payment-detail",
    ),
]
