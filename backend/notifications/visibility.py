from django.db.models import Q


NOISY_NOTIFICATION_TYPES = {"draft_autosaved"}
NOISY_METADATA_SOURCES = {"editor_autosave", "draft_autosave", "autosave", "draft_autosaved"}
NOISY_TEXT_PATTERNS = (
    "autosav",
    "draft saved",
    "draft autosaved",
    "background save",
    "snapshot synced",
    "snapshot sync",
)


def noisy_notification_q():
    query = Q(notification_type__in=NOISY_NOTIFICATION_TYPES) | Q(metadata__notification_hidden=True)
    for source in NOISY_METADATA_SOURCES:
        query |= Q(metadata__source__iexact=source)
        query |= Q(metadata__source_event__iexact=source)
    for pattern in NOISY_TEXT_PATTERNS:
        query |= Q(title__icontains=pattern) | Q(message__icontains=pattern)
    return query


def visible_notifications(queryset):
    noisy_ids = noisy_notifications(queryset.model.objects.all()).values("pk")
    return queryset.exclude(pk__in=noisy_ids)


def noisy_notifications(queryset):
    return queryset.filter(noisy_notification_q())
