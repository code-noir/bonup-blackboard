# backend/api/billing/urls.py

from django.urls import path

from .views import (
    BillingPortalAPIView,
    CheckoutSessionAPIView,
    InvoiceListAPIView,
    PlanListAPIView,
    SubscriptionAPIView,
    TrialStatusAPIView,
    UsageAPIView,
    WebhookAPIView,
)

urlpatterns = [
    path("plans/",        PlanListAPIView.as_view(),      name="billing-plans"),
    path("subscription/", SubscriptionAPIView.as_view(),  name="billing-subscription"),
    path("invoices/",     InvoiceListAPIView.as_view(),   name="billing-invoices"),
    path("usage/",        UsageAPIView.as_view(),         name="billing-usage"),
    path("trial/",        TrialStatusAPIView.as_view(),   name="billing-trial"),
    path("checkout/",     CheckoutSessionAPIView.as_view(), name="billing-checkout"),
    path("portal/",       BillingPortalAPIView.as_view(), name="billing-portal"),
    path("webhook/",      WebhookAPIView.as_view(),       name="billing-webhook"),
]
