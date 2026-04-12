# backend/api/contacts/views.py
#
# GET    /api/contacts/?search=   — all contacts owned by the logged-in user
# POST   /api/contacts/           — create (or return existing) contact for the logged-in user
# DELETE /api/contacts/{id}/      — delete a contact owned by the logged-in user
#
# Contacts are global to the bonID: no entity filter, no entity FK.

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.users.models import Contact


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "notes",
            "last_contracted",
            "added_at",
        ]
        read_only_fields = ["id", "added_at"]


class ContactListCreateView(APIView):
    """
    GET  /api/contacts/?search=<q>   List contacts for the logged-in user.
    POST /api/contacts/              Create a contact; idempotent on email.
    """

    def get(self, request):
        qs = Contact.objects.filter(owner=request.user)
        q = request.query_params.get("search", "").strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
            )
        return Response(ContactSerializer(qs, many=True).data)

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()

        # Idempotent: if a contact with this email already exists for the user,
        # return it rather than creating a duplicate.
        if email:
            existing = Contact.objects.filter(owner=request.user, email=email).first()
            if existing:
                return Response(ContactSerializer(existing).data, status=status.HTTP_200_OK)

        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contact = serializer.save(owner=request.user)
        return Response(ContactSerializer(contact).data, status=status.HTTP_201_CREATED)


class ContactDetailView(APIView):
    """DELETE /api/contacts/{contact_id}/"""

    def delete(self, request, contact_id):
        contact = get_object_or_404(Contact, pk=contact_id, owner=request.user)
        contact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
