# backend/core/urls.py




from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponseRedirect

from backend.api.router import urlpatterns as api_urls


def home(request):
    return HttpResponseRedirect("/api/")


urlpatterns = [
    path("", home),
    path("admin/", admin.site.urls),
    path("api/", include(api_urls)),
]








