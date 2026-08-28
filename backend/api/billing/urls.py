# backend/api/billing/urls.py

from django.urls import path

from .views import (
    BillingPortalAPIView,
    CheckoutSessionAPIView,
    InvoiceListAPIView,
    PlanListAPIView,
    StoreEligibilityAPIView,
    StoreQuoteAPIView,
    StoreStateAPIView,
    SubscriptionCatalogAPIView,
    SubscriptionAPIView,
    TrialStatusAPIView,
    UsageAPIView,
    WebhookAPIView,
)

urlpatterns = [
    path("catalog/",     SubscriptionCatalogAPIView.as_view(), name="billing-catalog"),
    path("plans/",        PlanListAPIView.as_view(),      name="billing-plans"),
    path("quote/",       StoreQuoteAPIView.as_view(),   name="billing-quote"),
    path("store/eligibility/", StoreEligibilityAPIView.as_view(), name="billing-store-eligibility"),
    path("store/state/", StoreStateAPIView.as_view(), name="billing-store-state"),
    path("subscription/", SubscriptionAPIView.as_view(),  name="billing-subscription"),
    path("invoices/",     InvoiceListAPIView.as_view(),   name="billing-invoices"),
    path("usage/",        UsageAPIView.as_view(),         name="billing-usage"),
    path("trial/",        TrialStatusAPIView.as_view(),   name="billing-trial"),
    path("checkout/",     CheckoutSessionAPIView.as_view(), name="billing-checkout"),
    path("portal/",       BillingPortalAPIView.as_view(), name="billing-portal"),
    path("webhook/",      WebhookAPIView.as_view(),       name="billing-webhook"),
]
