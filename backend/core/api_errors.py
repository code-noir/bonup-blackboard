"""Safe fallback for API errors; deliberate DRF/domain policies retain their status."""
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler, set_rollback
from backend.core.privacy_logging import safe_event


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        set_rollback()
        if isinstance(exc, ValidationError):
            response = Response({"detail": "Invalid request."}, status=400)
        else:
            safe_event("api_failure")
            response = Response({"detail": "Request could not be completed."}, status=500)
    if response.status_code == 404:
        response.data = {"detail": "Not found."}
    response["Cache-Control"] = "private, no-store"
    return response
