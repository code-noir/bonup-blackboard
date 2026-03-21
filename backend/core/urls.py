# backend/core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

from backend.api.router import urlpatterns as api_urls


# --------------------------------------------------
# ROOT (/)
# --------------------------------------------------
def home(request):
    return JsonResponse({
        "message": "Backend running",
        "go_to": "/api/",
    })


# --------------------------------------------------
# API ROOT (/api/)
# --------------------------------------------------
def api_root(request):
    return JsonResponse({
        "message": "API Root",
        "routes": [
            "/api/contracts/",
            "/api/contracts/<id>/obligations/",
            "/api/obligations/",
            "/api/payments/",
        ],
    })


# --------------------------------------------------
# URL PATTERNS
# --------------------------------------------------
urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),

    # exact /api/
    path("api/", api_root),

    # existing API router
    path("api/", include(api_urls)),

    # obligation domain
    path("api/obligations/", include("backend.api.obligations.urls")),
]








