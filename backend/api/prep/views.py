# backend/api/prep/views.py
#
# NegotiationPrep endpoints.
#
# Privacy rule: prep sessions are strictly private — only the owner may read
# or modify them.  No cross-party visibility at the API layer; that is
# handled separately via the WS broadcast mechanism.

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.negotiation_prep.models import PrepDocument, PrepNote, PrepSession
from backend.sessions.models import LiveSession


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _serialize_document(doc):
    return {
        "id": str(doc.id),
        "title": doc.title,
        "file_url": doc.file_url,
        "file_type": doc.file_type,
        "uploaded_at": doc.uploaded_at,
    }


def _serialize_note(note):
    return {
        "id": str(note.id),
        "content": note.content,
        "order": note.order,
        "created_at": note.created_at,
    }


def _serialize_prep(prep, include_children=False):
    data = {
        "id": str(prep.id),
        "live_session_id": str(prep.live_session_id) if prep.live_session_id else None,
        "owner_id": prep.owner_id,
        "title": prep.title,
        "notes": prep.notes,
        "created_at": prep.created_at,
        "updated_at": prep.updated_at,
    }
    if include_children:
        data["documents"] = [_serialize_document(d) for d in prep.documents.all()]
        data["notes_list"] = [_serialize_note(n) for n in prep.note_items.all()]
    return data


def _owner_only(prep, user):
    """Return True if *user* owns *prep*."""
    return prep.owner_id == user.pk


# ---------------------------------------------------------------------------
# /api/prep/
# ---------------------------------------------------------------------------

class PrepSessionListCreateAPIView(APIView):
    """
    GET  /api/prep/  — list the authenticated user's prep sessions
    POST /api/prep/  — create a prep session

    POST body:
      title           (required) string
      notes           (optional) string
      live_session_id (optional) UUID — link to an active live session
    """

    def get(self, request):
        qs = PrepSession.objects.filter(owner=request.user)
        return Response([_serialize_prep(p) for p in qs])

    def post(self, request):
        title = request.data.get("title", "").strip()
        if not title:
            return Response(
                {"error": "title is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        live_session = None
        live_session_id = request.data.get("live_session_id")
        if live_session_id:
            live_session = get_object_or_404(LiveSession, id=live_session_id)

        prep = PrepSession.objects.create(
            owner=request.user,
            title=title,
            notes=request.data.get("notes", ""),
            live_session=live_session,
        )
        return Response(_serialize_prep(prep), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# /api/prep/<prep_id>/
# ---------------------------------------------------------------------------

class PrepSessionDetailAPIView(APIView):
    """
    GET    /api/prep/<prep_id>/  — detail with all documents and notes
    PATCH  /api/prep/<prep_id>/  — update title and/or notes
    DELETE /api/prep/<prep_id>/  — delete the prep session
    """

    def _get_owned(self, request, prep_id):
        prep = get_object_or_404(PrepSession, id=prep_id)
        if not _owner_only(prep, request.user):
            return None, Response(
                {"error": "Not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return prep, None

    def get(self, request, prep_id):
        prep, err = self._get_owned(request, prep_id)
        if err:
            return err
        return Response(_serialize_prep(prep, include_children=True))

    def patch(self, request, prep_id):
        prep, err = self._get_owned(request, prep_id)
        if err:
            return err

        update_fields = ["updated_at"]
        if "title" in request.data:
            title = request.data["title"].strip()
            if not title:
                return Response(
                    {"error": "title cannot be blank."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            prep.title = title
            update_fields.append("title")
        if "notes" in request.data:
            prep.notes = request.data["notes"]
            update_fields.append("notes")

        prep.save(update_fields=update_fields)
        return Response(_serialize_prep(prep))

    def delete(self, request, prep_id):
        prep, err = self._get_owned(request, prep_id)
        if err:
            return err
        prep.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# /api/prep/<prep_id>/documents/
# ---------------------------------------------------------------------------

class PrepDocumentCreateAPIView(APIView):
    """
    POST /api/prep/<prep_id>/documents/

    Body: title (required), file_url (required), file_type (required: pdf/image/video/slides)
    """

    def post(self, request, prep_id):
        prep = get_object_or_404(PrepSession, id=prep_id)
        if not _owner_only(prep, request.user):
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        title = request.data.get("title", "").strip()
        file_url = request.data.get("file_url", "").strip()
        file_type = request.data.get("file_type", "").strip()

        if not title:
            return Response({"error": "title is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not file_url:
            return Response({"error": "file_url is required."}, status=status.HTTP_400_BAD_REQUEST)

        valid_types = [c[0] for c in PrepDocument.FILE_TYPE_CHOICES]
        if file_type not in valid_types:
            return Response(
                {"error": f"file_type must be one of: {', '.join(valid_types)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc = PrepDocument.objects.create(
            prep_session=prep,
            title=title,
            file_url=file_url,
            file_type=file_type,
        )
        return Response(_serialize_document(doc), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# /api/prep/<prep_id>/documents/<doc_id>/
# ---------------------------------------------------------------------------

class PrepDocumentDeleteAPIView(APIView):
    """
    DELETE /api/prep/<prep_id>/documents/<doc_id>/
    """

    def delete(self, request, prep_id, doc_id):
        prep = get_object_or_404(PrepSession, id=prep_id)
        if not _owner_only(prep, request.user):
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        doc = get_object_or_404(PrepDocument, id=doc_id, prep_session=prep)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# /api/prep/<prep_id>/notes/
# ---------------------------------------------------------------------------

class PrepNoteCreateAPIView(APIView):
    """
    POST /api/prep/<prep_id>/notes/

    Body: content (required), order (optional, default 0)
    """

    def post(self, request, prep_id):
        prep = get_object_or_404(PrepSession, id=prep_id)
        if not _owner_only(prep, request.user):
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get("content", "").strip()
        if not content:
            return Response({"error": "content is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = int(request.data.get("order", 0))
        except (ValueError, TypeError):
            order = 0

        note = PrepNote.objects.create(
            prep_session=prep,
            content=content,
            order=order,
        )
        return Response(_serialize_note(note), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# /api/prep/<prep_id>/notes/<note_id>/
# ---------------------------------------------------------------------------

class PrepNoteUpdateDeleteAPIView(APIView):
    """
    PATCH  /api/prep/<prep_id>/notes/<note_id>/  — update content and/or order
    DELETE /api/prep/<prep_id>/notes/<note_id>/  — delete note
    """

    def _get_note(self, request, prep_id, note_id):
        prep = get_object_or_404(PrepSession, id=prep_id)
        if not _owner_only(prep, request.user):
            return None, None, Response(
                {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
            )
        note = get_object_or_404(PrepNote, id=note_id, prep_session=prep)
        return prep, note, None

    def patch(self, request, prep_id, note_id):
        _, note, err = self._get_note(request, prep_id, note_id)
        if err:
            return err

        update_fields = []
        if "content" in request.data:
            content = request.data["content"].strip()
            if not content:
                return Response(
                    {"error": "content cannot be blank."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            note.content = content
            update_fields.append("content")
        if "order" in request.data:
            try:
                note.order = int(request.data["order"])
                update_fields.append("order")
            except (ValueError, TypeError):
                pass

        if update_fields:
            note.save(update_fields=update_fields)
        return Response(_serialize_note(note))

    def delete(self, request, prep_id, note_id):
        _, note, err = self._get_note(request, prep_id, note_id)
        if err:
            return err
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
