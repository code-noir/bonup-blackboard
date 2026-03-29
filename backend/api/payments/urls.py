from django.urls import path
from .views import (
    PaymentListCreateAPIView,
    PaymentDetailAPIView,
    PaymentConfirmAPIView,
    PaymentFailAPIView,
    PaymentCancelAPIView,
    PaymentRefundAPIView,
    PaymentReverseAPIView,
    ContractPaymentListCreateAPIView,
    ObligationPaymentListCreateAPIView,
    PaymentDashboardSummaryAPIView,
    ContractPaymentSummaryAPIView,
    ObligationPaymentSummaryAPIView,
)


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

    path(
    "<uuid:payment_id>/confirm/",
    PaymentConfirmAPIView.as_view(),
    name="payment-confirm",
    ),

    path(
        "<uuid:payment_id>/fail/",
        PaymentFailAPIView.as_view(),
        name="payment-fail",
    ),
    path(
        "<uuid:payment_id>/cancel/",
        PaymentCancelAPIView.as_view(),
        name="payment-cancel",
    ),
    path(
        "<uuid:payment_id>/refund/",
        PaymentRefundAPIView.as_view(),
        name="payment-refund",
    ),
    path(
        "<uuid:payment_id>/reverse/",
        PaymentReverseAPIView.as_view(),
        name="payment-reverse",
    ),

    path(
    "dashboard-summary/",
    PaymentDashboardSummaryAPIView.as_view(),
    name="payment-dashboard-summary",
    ),

    path(
        "contracts/<uuid:contract_id>/",
        ContractPaymentListCreateAPIView.as_view(),
        name="payment-contract-list-create",
    ),
    path(
        "contracts/<uuid:contract_id>/summary/",
        ContractPaymentSummaryAPIView.as_view(),
        name="payment-contract-summary",
    ),
    path(
        "obligations/<uuid:obligation_id>/",
        ObligationPaymentListCreateAPIView.as_view(),
        name="payment-obligation-list-create",
    ),
    path(
        "obligations/<uuid:obligation_id>/summary/",
        ObligationPaymentSummaryAPIView.as_view(),
        name="payment-obligation-summary",
    ),
]
