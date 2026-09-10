"""Allowlisted log output. Arbitrary messages, exceptions, and request data never render."""
import json
import logging
from contextvars import ContextVar
from uuid import UUID

request_id = ContextVar("privacy_request_id", default=None)
EVENTS = frozenset({"api_failure", "request_completed", "development_email_suppressed", "storage_failure"})


def safe_event(event, *, resource_id=None):
    if not isinstance(event, str) or event not in EVENTS:
        raise ValueError("Unknown logging event.")
    extra = {"privacy_event": event}
    if resource_id is not None:
        extra["resource_id"] = str(UUID(str(resource_id)))
    logging.getLogger("bonup.security").warning(event, extra=extra)


class PrivacyFormatter(logging.Formatter):
    def format(self, record):
        # Do not call getMessage(), formatException(), repr(), or serialize request/args.
        event = getattr(record, "privacy_event", None)
        if not isinstance(event, str) or event not in EVENTS:
            event = "request_completed" if record.name == "django.server" else "application_error" if record.levelno >= logging.ERROR else "application_event"
        data = {"event": event, "level": logging.getLevelName(record.levelno)}
        correlation = request_id.get()
        if correlation:
            data["request_id"] = correlation
        status = getattr(record, "status_code", None)
        if isinstance(status, int) and 100 <= status <= 599:
            data["status"] = status
        resource = getattr(record, "resource_id", None)
        if isinstance(resource, (str, UUID)) and resource:
            try:
                data["resource_id"] = str(UUID(str(resource)))
            except (ValueError, TypeError, AttributeError):
                pass
        return json.dumps(data, separators=(",", ":"))


LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"privacy": {"()": "backend.core.privacy_logging.PrivacyFormatter"}},
    "handlers": {"privacy": {"class": "logging.StreamHandler", "formatter": "privacy"}},
    "root": {"handlers": ["privacy"], "level": "INFO"},
    "loggers": {
        name: {"handlers": ["privacy"], "level": "INFO" if name in {"django", "django.server"} else "WARNING", "propagate": False}
        for name in ["django", "django.server", "botocore", "boto3", "urllib3", "httpx", "httpcore", "anthropic", "stripe", "daphne"]
    },
}
