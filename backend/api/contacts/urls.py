# backend/api/contacts/urls.py

from django.urls import path

from .views import ContactDetailView, ContactListCreateView

urlpatterns = [
    path("", ContactListCreateView.as_view(), name="contacts-list-create"),
    path("<uuid:contact_id>/", ContactDetailView.as_view(), name="contacts-detail"),
]
