from django.urls import path

from .views import (
    ProductDirectionTaskDetailView,
    ProductDirectionTaskListCreateView,
    ProductDirectionTaskProposalView,
    ProductDirectionTaskReviewAvailabilityView,
    ProductDirectionTaskReviewChallengeView,
    ProductDirectionTaskReviewSubmitView,
    ProductDirectionTaskReviewStatusView,
    ProductDirectionTaskSubmitView,
)


urlpatterns = [
    path("tasks/", ProductDirectionTaskListCreateView.as_view(), name="product-direction-task-list"),
    path("tasks/<uuid:task_id>/", ProductDirectionTaskDetailView.as_view(), name="product-direction-task-detail"),
    path("tasks/<uuid:task_id>/proposal/", ProductDirectionTaskProposalView.as_view(), name="product-direction-task-proposal"),
    path("tasks/<uuid:task_id>/submit/", ProductDirectionTaskSubmitView.as_view(), name="product-direction-task-submit"),
    path("tasks/<uuid:task_id>/review/availability/", ProductDirectionTaskReviewAvailabilityView.as_view(), name="product-direction-task-review-availability"),
    path("tasks/<uuid:task_id>/review/challenge/", ProductDirectionTaskReviewChallengeView.as_view(), name="product-direction-task-review-challenge"),
    path("tasks/<uuid:task_id>/review/submit/", ProductDirectionTaskReviewSubmitView.as_view(), name="product-direction-task-review-submit"),
    path("tasks/<uuid:task_id>/review/status/", ProductDirectionTaskReviewStatusView.as_view(), name="product-direction-task-review-status"),
]
