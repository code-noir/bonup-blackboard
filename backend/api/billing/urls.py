# backend/api/billing/urls.py

from django.urls import path

from .views import InvoiceListAPIView, PlanListAPIView, SubscriptionAPIView, TrialStatusAPIView, UsageAPIView

urlpatterns = [
    path("plans/", PlanListAPIView.as_view(), name="billing-plans"),
    path("subscription/", SubscriptionAPIView.as_view(), name="billing-subscription"),
    path("invoices/", InvoiceListAPIView.as_view(), name="billing-invoices"),
    path("usage/", UsageAPIView.as_view(), name="billing-usage"),
    path("trial/", TrialStatusAPIView.as_view(), name="billing-trial"),
]
