#backend/api/payments/__init__.py


from rest_framework import serializers
from backend.payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "contract",
            "payment_obligation",
            "payer",
            "payee",
            "amount",
            "currency",
            "status",
            "payment_method",
            "idempotency_key",
            "reference",
            "metadata",
            "created_at",
            "updated_at",
            "confirmed_at",
            "failed_at",
            "cancelled_at",
            "refunded_at",
            "reversed_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "confirmed_at",
            "failed_at",
            "cancelled_at",
            "refunded_at",
            "reversed_at",
        ]