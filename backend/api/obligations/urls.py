# backend/api/obligations/urls.py

from django.urls import path
from .views import ObligationDetailAPIView, ObligationTimelineAPIView

urlpatterns = [
    path(
        "<str:obligation_type>/<uuid:obligation_id>/",
        ObligationDetailAPIView.as_view(),
        name="obligation-detail",
    ),
    path(
        "<str:obligation_type>/<uuid:obligation_id>/timeline/",
        ObligationTimelineAPIView.as_view(),
        name="obligation-timeline",
    ),
]

