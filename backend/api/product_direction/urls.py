from django.urls import path

from .views import ProductDirectionTaskDetailView, ProductDirectionTaskListCreateView


urlpatterns = [
    path("tasks/", ProductDirectionTaskListCreateView.as_view(), name="product-direction-task-list"),
    path("tasks/<uuid:task_id>/", ProductDirectionTaskDetailView.as_view(), name="product-direction-task-detail"),
]
