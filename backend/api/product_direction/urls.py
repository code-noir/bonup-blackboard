from django.urls import path

from .views import (
    ProductDirectionTaskDetailView,
    ProductDirectionTaskListCreateView,
    ProductDirectionTaskProposalView,
    ProductDirectionTaskSubmitView,
)


urlpatterns = [
    path("tasks/", ProductDirectionTaskListCreateView.as_view(), name="product-direction-task-list"),
    path("tasks/<uuid:task_id>/", ProductDirectionTaskDetailView.as_view(), name="product-direction-task-detail"),
    path("tasks/<uuid:task_id>/proposal/", ProductDirectionTaskProposalView.as_view(), name="product-direction-task-proposal"),
    path("tasks/<uuid:task_id>/submit/", ProductDirectionTaskSubmitView.as_view(), name="product-direction-task-submit"),
]
