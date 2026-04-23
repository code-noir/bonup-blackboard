# backend/api/contacts/views.py
#
# DEFERRED — contacts domain is not active.
#
# The Contact model class was removed from backend/users/models.py.
# The DB table still exists (migration 0005_contact), but the ORM model
# is gone and this module is not mounted in api/router.py.
#
# These views are stubbed to fail safely at the API boundary.
# Do not mount this module or build on it until the Contact model
# is restored and the domain is explicitly re-activated.

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

_DEFERRED_RESPONSE = Response(
    {"detail": "Contacts domain is not active."},
    status=status.HTTP_501_NOT_IMPLEMENTED,
)


class ContactListCreateView(APIView):
    def get(self, request):
        return _DEFERRED_RESPONSE

    def post(self, request):
        return _DEFERRED_RESPONSE


class ContactDetailView(APIView):
    def delete(self, request, contact_id):
        return _DEFERRED_RESPONSE
