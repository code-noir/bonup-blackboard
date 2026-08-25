from django.urls import path

from backend.api.auth.views import OperatorTokenRefreshView

from .views import (
    OperatorMeView,
    OperatorTokenView,
    OperatorViewAsExitView,
    OperatorViewAsStartView,
)

urlpatterns = [
    path("auth/token/", OperatorTokenView.as_view(), name="operator-token"),
    path("auth/token/refresh/", OperatorTokenRefreshView.as_view(), name="operator-token-refresh"),
    path("me/", OperatorMeView.as_view(), name="operator-me"),
    path("view-as/<int:user_id>/", OperatorViewAsStartView.as_view(), name="operator-view-as-start"),
    path("view-as/exit/", OperatorViewAsExitView.as_view(), name="operator-view-as-exit"),
]
