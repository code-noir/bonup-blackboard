# backend/core/middleware.py
#
# Custom middleware for bonUP Blackboard.

from django.utils import translation


class UserLanguageMiddleware:
    """
    Activates the authenticated user's preferred language on every request.

    Must be placed after AuthenticationMiddleware in MIDDLEWARE so that
    request.user is already populated.

    Falls back gracefully — if the profile or language field is missing,
    the request proceeds with Django's default language resolution.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                lang = request.user.bon_profile.language
                if lang:
                    translation.activate(lang)
                    request.LANGUAGE_CODE = lang
            except Exception:
                pass

        response = self.get_response(request)
        translation.deactivate()
        return response


class PrivacyRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from uuid import uuid4
        from backend.core.privacy_logging import request_id
        correlation = str(uuid4())
        request.request_id = correlation
        token = request_id.set(correlation)
        try:
            from django.conf import settings
            from django.urls import reverse
            if settings.BONUP_THROTTLE_ENABLED and request.method == "POST" and request.path == reverse("admin:login"):
                from types import SimpleNamespace
                from django.http import JsonResponse
                from backend.core.throttling import PrivacyScopedThrottle
                import math
                throttle = PrivacyScopedThrottle()
                if not throttle.allow_request(request, SimpleNamespace(throttle_scope="operator_login")):
                    response = JsonResponse({"detail": "Too many login attempts."}, status=429)
                    response["Retry-After"] = str(math.ceil(throttle.wait() or 1))
                    response["Cache-Control"] = "no-store"
                    response["X-Request-ID"] = correlation
                    return response
            response = self.get_response(request)
            response["X-Request-ID"] = correlation
            return response
        finally:
            request_id.reset(token)
