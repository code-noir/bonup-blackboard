from django.core.management.base import BaseCommand

from backend.notifications.models import Notification
from backend.notifications.visibility import noisy_notifications


class Command(BaseCommand):
    help = "Hide autosave/background-save notification noise. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Mark noisy notifications read and hidden.")
        parser.add_argument("--limit", type=int, default=20, help="Number of sample rows to print.")

    def handle(self, *args, **options):
        apply = options["apply"]
        limit = max(0, options["limit"])
        queryset = noisy_notifications(Notification.objects.all()).order_by("-created_at")
        count = queryset.count()
        action = "Updated" if apply else "Would update"
        self.stdout.write(f"{action} {count} noisy autosave/system notification row(s).")

        samples = list(queryset[:limit])
        for item in samples:
            self.stdout.write(
                f"id={item.id} type={item.notification_type} title={item.title!r} message={item.message!r}"
            )

        if not apply:
            return

        for item in queryset.iterator():
            metadata = dict(item.metadata or {})
            metadata["notification_hidden"] = True
            metadata["hidden_reason"] = "autosave_or_background_save_noise"
            item.is_read = True
            item.metadata = metadata
            item.save(update_fields=["is_read", "metadata"])
