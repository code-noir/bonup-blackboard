import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.utils import timezone

from backend.operator.models import AdministratorAccount
from backend.operator.services import validate_administrator_user
from backend.users.models import BonUserProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Create a dedicated bonUP AdministratorAccount for an existing bonUP User."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, help="Existing bonUP User id to link.")
        parser.add_argument("--bon-id", help="Existing bonUP User bonID to link.")
        parser.add_argument("--email", help="Administrator email address.")
        parser.add_argument("--first-name", default="", help="Administrator first name.")
        parser.add_argument("--last-name", default="", help="Administrator last name.")
        parser.add_argument("--super-admin", action="store_true", help="Grant platform owner capability.")
        parser.add_argument("--can-view-as-user", action="store_true", help="Allow read-only View-As sessions.")
        parser.add_argument("--inactive", action="store_true", help="Create the account inactive.")

    def _resolve_user(self, *, user_id, bon_id):
        if bool(user_id) == bool(bon_id):
            raise CommandError("Provide exactly one of --user-id or --bon-id.")
        try:
            if user_id:
                return User.objects.select_related("bon_profile").get(pk=user_id)
            profile = BonUserProfile.objects.select_related("user").get(bon_id=bon_id)
            return profile.user
        except (User.DoesNotExist, BonUserProfile.DoesNotExist) as exc:
            raise CommandError("No existing bonUP User was found for that identifier.") from exc

    def handle(self, *args, **options):
        user = self._resolve_user(
            user_id=options.get("user_id"),
            bon_id=(options.get("bon_id") or "").strip(),
        )
        try:
            profile = validate_administrator_user(user)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc

        if AdministratorAccount.objects.filter(user=user, is_legacy_placeholder=False).exists():
            raise CommandError("This bonUP User already has a real AdministratorAccount.")

        email = (options.get("email") or input("Administrator email: ")).strip().lower()
        try:
            validate_email(email)
        except Exception as exc:
            raise CommandError("Enter a valid administrator email address.") from exc

        if AdministratorAccount.objects.filter(email__iexact=email).exists():
            raise CommandError("An administrator account with this email already exists.")

        self.stdout.write("Linking administrator identity to existing bonUP User:")
        self.stdout.write(f"  User.id: {user.pk}")
        self.stdout.write(f"  User.email: {user.email}")
        self.stdout.write(f"  User.is_active: {user.is_active}")
        self.stdout.write(f"  BonUserProfile.email_verified: {profile.email_verified}")
        self.stdout.write(f"  bonID: {profile.bon_id}")
        self.stdout.write(f"  Administrator email: {email}")

        password = getpass.getpass("Administrator password: ")
        password_confirm = getpass.getpass("Confirm administrator password: ")
        if not password:
            raise CommandError("Password cannot be blank.")
        if password != password_confirm:
            raise CommandError("Passwords do not match.")
        try:
            validate_password(password, user=user)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        administrator = AdministratorAccount(
            user=user,
            email=email,
            first_name=(options.get("first_name") or "").strip(),
            last_name=(options.get("last_name") or "").strip(),
            is_active=not options.get("inactive"),
            is_super_admin=bool(options.get("super_admin")),
            can_view_as_user=bool(options.get("can_view_as_user") or options.get("super_admin")),
            is_legacy_placeholder=False,
            last_login_at=None,
        )
        administrator.set_password(password)
        try:
            administrator.save()
        except IntegrityError as exc:
            raise CommandError("Could not create administrator account; email or linked User may already exist.") from exc

        self.stdout.write(self.style.SUCCESS(
            f"Created administrator account {administrator.email} linked to bonID {profile.bon_id} at {timezone.now().isoformat()}"
        ))
