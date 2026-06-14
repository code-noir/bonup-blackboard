from django.core.management.base import BaseCommand

from backend.lifecycle.services import backfill_signed_exchange_versions


class Command(BaseCommand):
    help = "Backfill signed Agreement Exchange current versions to signed status. Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Apply the backfill. Without this flag, only report rows.")

    def handle(self, *args, **options):
        apply = options["apply"]
        rows = backfill_signed_exchange_versions(apply=apply)
        action = "Updated" if apply else "Would update"
        self.stdout.write(f"{action} {len(rows)} signed Agreement Exchange version row(s).")
        for row in rows:
            self.stdout.write(
                "exchange={exchange_id} contract={contract_id} version={version_id} "
                "version_status={version_status} contract_status={contract_status}".format(**row)
            )
