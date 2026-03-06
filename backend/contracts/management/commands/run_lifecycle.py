from django.utils import timezone
from django.core.management.base import BaseCommand
from backend.engine.automation.execute import execute_lifecycle_automation


class Command(BaseCommand):
    help = "Run lifecycle automation manually."

    def add_arguments(self, parser):
        parser.add_argument(
            "--contract-id",
            type=int,
            help="Optional contract ID to restrict automation.",
        )

        parser.add_argument(
            "--limit",
            type=int,
            help="Optional limit of obligations to scan.",
        )

    def handle(self, *args, **options):
        contract_id = options.get("contract_id")
        limit = options.get("limit")

        self.stdout.write(self.style.NOTICE("Running lifecycle automation..."))

        result = execute_lifecycle_automation(
            contract_id=contract_id,
            limit=limit,
            current_time=timezone.now(),  # ✅ FIXED
        )

        self.stdout.write(self.style.SUCCESS("Automation complete."))
        self.stdout.write(
            f"Scanned: {result.scanned}, "
            f"Updated: {result.updated}, "
            f"Unchanged: {result.unchanged}"
        )



