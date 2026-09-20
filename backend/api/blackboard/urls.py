from django.urls import path

from .views import ApprovedProductDirectionListView


urlpatterns = [
    path("product-direction/approved/", ApprovedProductDirectionListView.as_view(),
         name="blackboard-approved-product-direction"),
]
