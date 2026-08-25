from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView

from .views import EmailOrUsernameTokenView, NormalTokenRefreshView

urlpatterns = [
    path("token/", EmailOrUsernameTokenView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", NormalTokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),
]
