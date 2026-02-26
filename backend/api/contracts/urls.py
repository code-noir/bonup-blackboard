from django.urls import path
from .views import CreateContractAPIView

urlpatterns = [
    path("", CreateContractAPIView.as_view(), name="create-contract"),
]

