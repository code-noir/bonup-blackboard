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
