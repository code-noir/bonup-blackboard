"""Environment-only production safeguards; importing this module performs no I/O."""
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def boolean(env, name, default=False):
    value = str(env.get(name, str(default))).strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise ImproperlyConfigured(f"{name} must be true or false.")
    return value in {"true", "1"}


def security_settings(env, *, development_hosts=None):
    mode = env.get("BONUP_ENV", "development").strip().lower()
    if mode not in {"development", "test", "production"}:
        raise ImproperlyConfigured("BONUP_ENV must be development, test, or production.")
    production = mode == "production"
    debug = boolean(env, "DJANGO_DEBUG")
    hosts = [item.strip() for item in env.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if item.strip()]
    if not production and "DJANGO_ALLOWED_HOSTS" not in env and development_hosts is not None:
        hosts = list(development_hosts)
    origins = [item.strip() for item in env.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if item.strip()]
    trusted_proxy = boolean(env, "BONUP_TRUST_PROXY")
    email_backend = env.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
    tls, ssl = boolean(env, "EMAIL_USE_TLS"), boolean(env, "EMAIL_USE_SSL")
    if tls and ssl:
        raise ImproperlyConfigured("SMTP TLS and SSL cannot both be enabled.")
    if production:
        if debug:
            raise ImproperlyConfigured("Production requires DJANGO_DEBUG=False.")
        secret = env.get("SECRET_KEY", "")
        if len(secret) < 50 or len(set(secret)) < 5 or secret.startswith("django-insecure-"):
            raise ImproperlyConfigured("Production requires a strong SECRET_KEY.")
        if not env.get("DJANGO_ALLOWED_HOSTS") or not hosts or any("*" in host or "/" in host or host.startswith(".") for host in hosts):
            raise ImproperlyConfigured("Production requires explicit DJANGO_ALLOWED_HOSTS without wildcards.")
        frontend = urlsplit(env.get("FRONTEND_URL", ""))
        if frontend.scheme != "https" or not frontend.hostname or frontend.username or frontend.password:
            raise ImproperlyConfigured("Production requires an HTTPS FRONTEND_URL.")
        if any(urlsplit(origin).scheme != "https" or not urlsplit(origin).hostname or "*" in origin for origin in origins):
            raise ImproperlyConfigured("Production CSRF origins must be explicit HTTPS origins.")
        if email_backend not in {"backend.core.email_backends.ResendEmailBackend", "django.core.mail.backends.smtp.EmailBackend"}:
            raise ImproperlyConfigured("Production requires an explicit delivery email backend.")
        if not env.get("DEFAULT_FROM_EMAIL"):
            raise ImproperlyConfigured("Production requires DEFAULT_FROM_EMAIL.")
        if urlsplit(env.get("RESEND_API_URL", "https://api.resend.com/emails")).scheme != "https":
            raise ImproperlyConfigured("Production email provider transport requires HTTPS.")
        if email_backend.endswith("ResendEmailBackend") and not env.get("RESEND_API_KEY"):
            raise ImproperlyConfigured("Production email credentials are required.")
        if email_backend.endswith("smtp.EmailBackend"):
            if not env.get("EMAIL_HOST") or tls == ssl:
                raise ImproperlyConfigured("Production SMTP requires a host and exactly one TLS/SSL transport.")
        if env.get("BONUP_EMAIL_PROVIDER", "resend") == "resend" and (not env.get("RESEND_API_KEY") or not env.get("BONUP_EMAIL_FROM")):
            raise ImproperlyConfigured("Production Vault email configuration is required.")
    # Console email contains bearer links. Development keeps HTTP, not secret dumps.
    elif email_backend == "django.core.mail.backends.console.EmailBackend":
        email_backend = "backend.core.email_backends.PrivacyConsoleEmailBackend"
    try:
        hsts = int(env.get("BONUP_HSTS_SECONDS", "0"))
    except ValueError:
        raise ImproperlyConfigured("BONUP_HSTS_SECONDS must be a nonnegative integer.") from None
    if hsts < 0:
        raise ImproperlyConfigured("BONUP_HSTS_SECONDS must be a nonnegative integer.")
    return {
        "BONUP_ENV": mode, "BONUP_PRODUCTION": production,
        "DEBUG": debug, "ALLOWED_HOSTS": hosts, "CSRF_TRUSTED_ORIGINS": origins,
        "SECURE_SSL_REDIRECT": production,
        # Enable only after the edge overwrites forwarded headers and the app port is private.
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https") if production and trusted_proxy else None,
        "USE_X_FORWARDED_HOST": False,
        "SESSION_COOKIE_SECURE": production, "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax", "CSRF_COOKIE_SECURE": production,
        "CSRF_COOKIE_HTTPONLY": False, "CSRF_COOKIE_SAMESITE": "Lax",
        "SECURE_HSTS_SECONDS": hsts if production else 0,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": False, "SECURE_HSTS_PRELOAD": False,
        "SECURE_CONTENT_TYPE_NOSNIFF": True, "X_FRAME_OPTIONS": "DENY",
        "SECURE_REFERRER_POLICY": "no-referrer", "EMAIL_BACKEND": email_backend,
        "EMAIL_USE_TLS": tls, "EMAIL_USE_SSL": ssl,
        "BONUP_TRUST_PROXY": production and trusted_proxy,
        "BONUP_THROTTLE_ENABLED": production or boolean(env, "BONUP_THROTTLE_ENABLED"),
    }
