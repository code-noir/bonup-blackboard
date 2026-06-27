from django.core.management.base import BaseCommand

from backend.lifecycle.reminders import send_due_timeline_reminders


class Command(BaseCommand):
    help = "Send due personal Agreement Performance reminder notifications."

    def handle(self, *args, **options):
        sent = send_due_timeline_reminders()
        self.stdout.write(f"Sent {len(sent)} reminder notification(s).")
