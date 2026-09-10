"""Small scoped abuse controls. LocMem limits are per process, not a DDoS boundary."""
from django.conf import settings
from django.utils.crypto import salted_hmac
from rest_framework.throttling import SimpleRateThrottle

DEFAULT_RATES = {
    "login": "10/min", "operator_login": "5/min", "refresh": "30/min",
    "recovery": "5/hour", "share_metadata": "60/min", "share_delivery": "120/min",
    "share_create": "30/hour", "upload": "20/min", "bulk_download": "10/min",
    "email": "20/min", "search": "60/min", "ai": "10/min",
}


def client_ip(request):
    # Only a verified, single edge may supply the client address. It MUST overwrite XFF.
    if settings.BONUP_TRUST_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded and "," not in forwarded:
            return forwarded.strip()
    return request.META.get("REMOTE_ADDR", "")


class PrivacyScopedThrottle(SimpleRateThrottle):
    def __init__(self):
        # Scope depends on the resolved view/action, not a URL denylist.
        pass

    def allow_request(self, request, view):
        if not settings.BONUP_THROTTLE_ENABLED:
            return True
        self.scope = getattr(view, "throttle_scopes", {}).get(getattr(view, "action", None), getattr(view, "throttle_scope", None))
        if not self.scope:
            return True
        rates = getattr(settings, "BONUP_THROTTLE_RATES", DEFAULT_RATES)
        self.rate = rates[self.scope]
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        public = self.scope in {"login", "operator_login", "refresh", "recovery", "share_metadata", "share_delivery"}
        identity = f"ip:{client_ip(request)}"
        if not public and request.user.is_authenticated:
            identity = f"user:{request.user.pk}"
        digest = salted_hmac("bonup-throttle", identity).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}
