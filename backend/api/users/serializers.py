# backend/api/users/serializers.py

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from backend.users.models import BonUserProfile, BusinessEntity, PendingSignup, UserBillingInfo, UserInvitation

User = get_user_model()


class PendingSignupSerializer(serializers.Serializer):
    """
    Validates a signup form submission and creates a PendingSignup record.

    No User, BonUserProfile, or bonID is created here.  The real account is
    created only after the user clicks the verification link (VerifyPendingEmailAPIView).
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        if PendingSignup.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A verification email was already sent to this address. "
                "Check your inbox or request a new verification link."
            )
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return PendingSignup.objects.create(
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            email=validated_data["email"],
            password_hash=make_password(validated_data["password"]),
            expires_at=timezone.now() + timedelta(hours=PendingSignup.EXPIRY_HOURS),
        )


class RegisterSerializer(serializers.Serializer):
    """
    Direct user creation — used only by the invitation acceptance flow.
    The inviter's email is implicitly verified by the invitation token,
    so no PendingSignup staging is needed.
    """

    # No username — email is the external identity anchor.
    # Username is an internal Django field; we set it to email automatically.
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        email = validated_data["email"]
        # Username is an internal field — set it to email so Django's auth layer
        # is satisfied. It is never shown or used by the product experience.
        return User.objects.create_user(
            username=email,
            email=email,
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
        )


class UserProfileSerializer(serializers.Serializer):
    """
    Composite read serializer across User + BonUserProfile.
    Used for /me/ and profile retrieve endpoints.
    """

    # From User
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)

    # From BonUserProfile
    bon_id = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    state_region = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()
    business_count = serializers.SerializerMethodField()
    max_businesses = serializers.SerializerMethodField()

    # From billing
    subscription_tier = serializers.SerializerMethodField()
    effective_blackbod_tier = serializers.SerializerMethodField()
    has_blackbod_access = serializers.SerializerMethodField()
    trial_start = serializers.SerializerMethodField()
    trial_end = serializers.SerializerMethodField()
    trial_valid = serializers.SerializerMethodField()

    def _profile(self, obj):
        try:
            return obj.bon_profile
        except BonUserProfile.DoesNotExist:
            return None

    def get_bon_id(self, obj):
        p = self._profile(obj)
        return p.bon_id if p else None

    def get_phone(self, obj):
        p = self._profile(obj)
        return p.phone if p else None

    def get_city(self, obj):
        p = self._profile(obj)
        return p.city if p else None

    def get_state_region(self, obj):
        p = self._profile(obj)
        return p.state_region if p else None

    def get_country(self, obj):
        p = self._profile(obj)
        return p.country if p else None

    def get_email_verified(self, obj):
        p = self._profile(obj)
        return p.email_verified if p else False

    def get_business_count(self, obj):
        return BusinessEntity.objects.filter(owner=obj, is_active=True).count()

    def get_max_businesses(self, obj):
        from backend.billing.gates import max_businesses as _max_businesses
        return _max_businesses(obj)

    def get_subscription_tier(self, obj):
        try:
            return obj.subscription.plan.slug
        except Exception:
            return None

    def get_effective_blackbod_tier(self, obj):
        from backend.billing.gates import get_effective_blackbod_tier
        return get_effective_blackbod_tier(obj)

    def get_has_blackbod_access(self, obj):
        from backend.billing.blackbod import has_blackbod_access
        return has_blackbod_access(obj)

    def get_trial_start(self, obj):
        try:
            return obj.subscription.trial_start
        except Exception:
            return None

    def get_trial_end(self, obj):
        try:
            return obj.subscription.trial_end
        except Exception:
            return None

    def get_trial_valid(self, obj):
        from backend.billing.gates import is_trial_valid
        try:
            return is_trial_valid(obj.subscription)
        except Exception:
            return False


class PublicUserSerializer(serializers.Serializer):
    """
    Minimal public identity — used for bonID lookup / discovery.
    """

    bon_id = serializers.CharField(source="bon_profile.bon_id", read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )
        return attrs


class UpdateEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField()

    def validate_new_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value


class UpdatePhoneSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=30, allow_blank=True)


class UpdateLocationSerializer(serializers.Serializer):
    city = serializers.CharField(max_length=100, allow_blank=True, required=False)
    state_region = serializers.CharField(max_length=100, allow_blank=True, required=False)
    country = serializers.CharField(max_length=100, allow_blank=True, required=False)


class UserBillingInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBillingInfo
        fields = [
            "billing_name",
            "address_line_1",
            "address_line_2",
            "city",
            "state_region",
            "country",
            "postal_code",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]


class UserInvitationSerializer(serializers.ModelSerializer):
    # token is in the URL — never expose it in the response body
    class Meta:
        model = UserInvitation
        fields = [
            "id",
            "invitee_email",
            "invitee_name",
            "status",
            "created_at",
            "expires_at",
        ]
        read_only_fields = ["id", "status", "created_at"]
