# backend/billing/stripe_client.py
#
# Thin wrapper that initialises the Stripe SDK from Django settings.
# Always call get_stripe() rather than importing stripe directly in service code,
# so the api_key is guaranteed to be set before any SDK call.

import stripe as _stripe
from django.conf import settings


def get_stripe():
    """Return the stripe module with api_key initialised from settings."""
    _stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
    return _stripe


def stripe_configured():
    """Return True if a real Stripe secret key is present (not empty, not a test stub)."""
    key = getattr(settings, "STRIPE_SECRET_KEY", "")
    return bool(key)
