from django.urls import path

from .views import (
    AgreementExchangeCreateAPIView,
    AgreementExchangeDetailAPIView,
    AgreementExchangeFromWorkflowAPIView,
    AgreementExchangeRejectAPIView,
    AgreementExchangeRebuildStagedVersionAPIView,
    AgreementExchangeRequestListCreateAPIView,
    AgreementExchangeRequestRespondAPIView,
    AgreementExchangeRestartAPIView,
    AgreementExchangeSaveStagedVersionAPIView,
    AgreementExchangeSendInitialAPIView,
    AgreementExchangeSendUpdatedVersionAPIView,
    AgreementExchangeSignAPIView,
    AgreementExchangeTemplateAPIView,
    AgreementExchangeViewedAPIView,
)

urlpatterns = [
    path("from-workflow/", AgreementExchangeFromWorkflowAPIView.as_view()),
    path("", AgreementExchangeCreateAPIView.as_view()),
    path("templates/", AgreementExchangeTemplateAPIView.as_view()),
    path("<uuid:exchange_id>/", AgreementExchangeDetailAPIView.as_view()),
    path("<uuid:exchange_id>/viewed/", AgreementExchangeViewedAPIView.as_view()),
    path("<uuid:exchange_id>/send-initial/", AgreementExchangeSendInitialAPIView.as_view()),
    path("<uuid:exchange_id>/restart/", AgreementExchangeRestartAPIView.as_view()),
    path("<uuid:exchange_id>/requests/", AgreementExchangeRequestListCreateAPIView.as_view()),
    path("<uuid:exchange_id>/requests/<uuid:request_id>/respond/", AgreementExchangeRequestRespondAPIView.as_view()),
    path("<uuid:exchange_id>/rebuild-staged-version/", AgreementExchangeRebuildStagedVersionAPIView.as_view()),
    path("<uuid:exchange_id>/save-staged-version/", AgreementExchangeSaveStagedVersionAPIView.as_view()),
    path("<uuid:exchange_id>/send-updated-version/", AgreementExchangeSendUpdatedVersionAPIView.as_view()),
    path("<uuid:exchange_id>/sign/", AgreementExchangeSignAPIView.as_view()),
    path("<uuid:exchange_id>/reject/", AgreementExchangeRejectAPIView.as_view()),
]
