from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.permissions import (
    contract_party_response,
    is_party,
)
from backend.contracts.models import Contract, ContractObligation
from backend.engine.contracts.obligations.lifecycle import process_obligation_lifecycle
from backend.payments.models import Payment
from .serializers import PaymentSerializer

# Valid source states for each status transition endpoint.
ALLOWED_FROM = {
    "pending":   {"draft"},
    "confirmed": {"pending"},
    "failed":    {"pending"},
    "cancelled": {"draft", "pending"},
    "refunded":  {"confirmed"},
    "reversed":  {"confirmed"},
}

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _idempotency_response(key):
    """Return the existing payment if a duplicate idempotency_key is submitted."""
    try:
        payment = Payment.objects.get(idempotency_key=key)
        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)
    except Payment.DoesNotExist:
        return None


def _party_q(user):
    """Q filter that scopes payments to contracts the user is a party to."""
    return Q(contract__initiator=user) | Q(contract__counterparty_email=user.email)


def _apply_filters(queryset, request):
    """Apply common query-param filters to a Payment queryset."""
    qs = queryset

    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)

    method_filter = request.query_params.get("payment_method")
    if method_filter:
        qs = qs.filter(payment_method=method_filter)

    created_after = request.query_params.get("created_after")
    if created_after:
        qs = qs.filter(created_at__gte=created_after)

    created_before = request.query_params.get("created_before")
    if created_before:
        qs = qs.filter(created_at__lte=created_before)

    return qs


def _paginated_response(queryset, request):
    """Paginate a queryset and return a Response with envelope."""
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = min(MAX_PAGE_SIZE, max(1, int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE))))
    except (ValueError, TypeError):
        page_size = DEFAULT_PAGE_SIZE

    total = queryset.count()
    offset = (page - 1) * page_size
    results = PaymentSerializer(queryset[offset:offset + page_size], many=True).data

    return Response({
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": results,
    }, status=status.HTTP_200_OK)


class PaymentListCreateAPIView(APIView):
    """
    GET  /api/payments/
    POST /api/payments/
    """

    def get(self, request):
        qs = _apply_filters(
            Payment.objects.filter(_party_q(request.user)),
            request,
        ).order_by("-created_at")
        return _paginated_response(qs, request)

    def post(self, request):
        idem_key = request.data.get("idempotency_key")
        if idem_key:
            existing = _idempotency_response(idem_key)
            if existing is not None:
                return existing

        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Verify the user is a party to the contract on this payment
        contract_id = serializer.validated_data.get("contract_id") or (
            serializer.validated_data.get("contract").id
            if serializer.validated_data.get("contract")
            else None
        )
        if contract_id:
            contract = get_object_or_404(Contract, id=contract_id)
            if not is_party(request.user, contract):
                return contract_party_response()

        with transaction.atomic():
            payment = serializer.save()
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentDetailAPIView(APIView):
    """
    GET    /api/payments/<payment_id>/
    PATCH  /api/payments/<payment_id>/
    DELETE /api/payments/<payment_id>/
    """

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()
        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)

    def patch(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        serializer = PaymentSerializer(payment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            payment = serializer.save()
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        payment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentConfirmAPIView(APIView):
    """
    POST /api/payments/<payment_id>/confirm/
    """

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        if payment.status not in ALLOWED_FROM["confirmed"]:
            return Response(
                {"error": f"Cannot confirm a payment with status '{payment.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()

        with transaction.atomic():
            # 1. Mark payment confirmed
            payment.status = "confirmed"
            payment.confirmed_at = now
            payment.failed_at = None
            payment.cancelled_at = None
            payment.refunded_at = None
            payment.reversed_at = None
            payment.save(
                update_fields=[
                    "status",
                    "confirmed_at",
                    "failed_at",
                    "cancelled_at",
                    "refunded_at",
                    "reversed_at",
                    "updated_at",
                ]
            )

            # 2. Sync obligation balance and state if linked
            if payment.payment_obligation_id:
                obligation = ContractObligation.objects.select_for_update().get(
                    id=payment.payment_obligation_id
                )

                # Recompute from all confirmed payments (authoritative total)
                confirmed_total = (
                    Payment.objects
                    .filter(payment_obligation_id=obligation.id, status="confirmed")
                    .aggregate(total=Sum("amount"))["total"]
                ) or Decimal("0")

                obligation.amount_paid = confirmed_total

                # Re-evaluate lifecycle state via engine
                process_obligation_lifecycle(
                    obligation,
                    obligation_repo=None,
                    current_time=now,
                )

                obligation.is_defaulted = obligation.state in ("defaulted", "breached")
                obligation.updated_at = now
                obligation.save(
                    update_fields=["amount_paid", "state", "is_defaulted", "updated_at"]
                )

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentPendingAPIView(APIView):
    """
    POST /api/payments/<payment_id>/pending/
    """

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        if payment.status not in ALLOWED_FROM["pending"]:
            return Response(
                {"error": f"Cannot mark pending a payment with status '{payment.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            payment.status = "pending"
            payment.save(update_fields=["status", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentFailAPIView(APIView):
    """
    POST /api/payments/<payment_id>/fail/
    """

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        if payment.status not in ALLOWED_FROM["failed"]:
            return Response(
                {"error": f"Cannot fail a payment with status '{payment.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            payment.status = "failed"
            payment.failed_at = timezone.now()
            payment.save(update_fields=["status", "failed_at", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentCancelAPIView(APIView):
    """
    POST /api/payments/<payment_id>/cancel/
    """

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        if payment.status not in ALLOWED_FROM["cancelled"]:
            return Response(
                {"error": f"Cannot cancel a payment with status '{payment.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            payment.status = "cancelled"
            payment.cancelled_at = timezone.now()
            payment.save(update_fields=["status", "cancelled_at", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentRefundAPIView(APIView):
    """
    POST /api/payments/<payment_id>/refund/
    """

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        if payment.status not in ALLOWED_FROM["refunded"]:
            return Response(
                {"error": f"Cannot refund a payment with status '{payment.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()

        with transaction.atomic():
            payment.status = "refunded"
            payment.refunded_at = now
            payment.save(update_fields=["status", "refunded_at", "updated_at"])

            if payment.payment_obligation_id:
                obligation = ContractObligation.objects.select_for_update().get(
                    id=payment.payment_obligation_id
                )
                confirmed_total = (
                    Payment.objects
                    .filter(payment_obligation_id=obligation.id, status="confirmed")
                    .aggregate(total=Sum("amount"))["total"]
                ) or Decimal("0")
                obligation.amount_paid = confirmed_total
                process_obligation_lifecycle(obligation, obligation_repo=None, current_time=now)
                obligation.is_defaulted = obligation.state in ("defaulted", "breached")
                obligation.updated_at = now
                obligation.save(update_fields=["amount_paid", "state", "is_defaulted", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentReverseAPIView(APIView):
    """
    POST /api/payments/<payment_id>/reverse/
    """

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, id=payment_id)
        if not is_party(request.user, payment.contract):
            return contract_party_response()

        if payment.status not in ALLOWED_FROM["reversed"]:
            return Response(
                {"error": f"Cannot reverse a payment with status '{payment.status}'."},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()

        with transaction.atomic():
            payment.status = "reversed"
            payment.reversed_at = now
            payment.save(update_fields=["status", "reversed_at", "updated_at"])

            if payment.payment_obligation_id:
                obligation = ContractObligation.objects.select_for_update().get(
                    id=payment.payment_obligation_id
                )
                confirmed_total = (
                    Payment.objects
                    .filter(payment_obligation_id=obligation.id, status="confirmed")
                    .aggregate(total=Sum("amount"))["total"]
                ) or Decimal("0")
                obligation.amount_paid = confirmed_total
                process_obligation_lifecycle(obligation, obligation_repo=None, current_time=now)
                obligation.is_defaulted = obligation.state in ("defaulted", "breached")
                obligation.updated_at = now
                obligation.save(update_fields=["amount_paid", "state", "is_defaulted", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class ContractPaymentListCreateAPIView(APIView):
    """
    GET  /api/payments/contracts/<contract_id>/
    POST /api/payments/contracts/<contract_id>/
    """

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        qs = _apply_filters(
            Payment.objects.filter(contract_id=contract_id),
            request,
        ).order_by("-created_at")
        return _paginated_response(qs, request)

    def post(self, request, contract_id):
        idem_key = request.data.get("idempotency_key")
        if idem_key:
            existing = _idempotency_response(idem_key)
            if existing is not None:
                return existing

        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        data = request.data.copy()
        data["contract"] = str(contract.id)

        serializer = PaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            payment = serializer.save()

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class ObligationPaymentListCreateAPIView(APIView):
    """
    GET  /api/payments/obligations/<obligation_id>/
    POST /api/payments/obligations/<obligation_id>/
    """

    def get(self, request, obligation_id):
        obligation = get_object_or_404(ContractObligation, id=obligation_id)
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        qs = _apply_filters(
            Payment.objects.filter(payment_obligation_id=obligation_id),
            request,
        ).order_by("-created_at")
        return _paginated_response(qs, request)

    def post(self, request, obligation_id):
        idem_key = request.data.get("idempotency_key")
        if idem_key:
            existing = _idempotency_response(idem_key)
            if existing is not None:
                return existing

        obligation = get_object_or_404(ContractObligation, id=obligation_id)
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        TERMINAL_STATES = {"resolved", "breached", "defaulted"}
        if obligation.state in TERMINAL_STATES:
            return Response(
                {"error": f"Cannot add a payment to an obligation with status '{obligation.state}'."},
                status=status.HTTP_409_CONFLICT,
            )

        data = request.data.copy()
        data["contract"] = str(obligation.contract_id)
        data["payment_obligation"] = str(obligation.id)

        serializer = PaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            payment = serializer.save()

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )


class PaymentDashboardSummaryAPIView(APIView):
    """
    GET /api/payments/dashboard-summary/
    """

    def get(self, request):
        payments = Payment.objects.filter(_party_q(request.user))

        total_amount = payments.aggregate(total=Sum("amount"))["total"] or 0
        confirmed_amount = payments.filter(status="confirmed").aggregate(total=Sum("amount"))["total"] or 0
        refunded_amount = payments.filter(status="refunded").aggregate(total=Sum("amount"))["total"] or 0
        reversed_amount = payments.filter(status="reversed").aggregate(total=Sum("amount"))["total"] or 0

        payload = {
            "count": payments.count(),
            "total_amount": str(total_amount),
            "confirmed_amount": str(confirmed_amount),
            "refunded_amount": str(refunded_amount),
            "reversed_amount": str(reversed_amount),
            "by_status": {
                "draft": payments.filter(status="draft").count(),
                "pending": payments.filter(status="pending").count(),
                "confirmed": payments.filter(status="confirmed").count(),
                "failed": payments.filter(status="failed").count(),
                "cancelled": payments.filter(status="cancelled").count(),
                "refunded": payments.filter(status="refunded").count(),
                "reversed": payments.filter(status="reversed").count(),
            },
        }

        return Response(payload, status=status.HTTP_200_OK)


class ContractPaymentSummaryAPIView(APIView):
    """
    GET /api/payments/contracts/<contract_id>/summary/
    """

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, id=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        payments = Payment.objects.filter(contract_id=contract.id)

        total_amount = payments.aggregate(total=Sum("amount"))["total"] or 0
        confirmed_amount = payments.filter(status="confirmed").aggregate(total=Sum("amount"))["total"] or 0
        refunded_amount = payments.filter(status="refunded").aggregate(total=Sum("amount"))["total"] or 0

        payload = {
            "contract_id": str(contract.id),
            "count": payments.count(),
            "total_amount": str(total_amount),
            "confirmed_amount": str(confirmed_amount),
            "refunded_amount": str(refunded_amount),
            "failed_count": payments.filter(status="failed").count(),
            "cancelled_count": payments.filter(status="cancelled").count(),
        }

        return Response(payload, status=status.HTTP_200_OK)


class ObligationPaymentSummaryAPIView(APIView):
    """
    GET /api/payments/obligations/<obligation_id>/summary/
    """

    def get(self, request, obligation_id):
        obligation = get_object_or_404(ContractObligation, id=obligation_id)
        if not is_party(request.user, obligation.contract):
            return contract_party_response()

        payments = Payment.objects.filter(payment_obligation_id=obligation.id)

        total_amount = payments.aggregate(total=Sum("amount"))["total"] or 0
        confirmed_amount = payments.filter(status="confirmed").aggregate(total=Sum("amount"))["total"] or 0
        refunded_amount = payments.filter(status="refunded").aggregate(total=Sum("amount"))["total"] or 0

        remaining_balance = obligation.amount_due - obligation.amount_paid

        payload = {
            "obligation_id": str(obligation.id),
            "contract_id": str(obligation.contract_id),
            "obligation_state": obligation.state,
            "amount_due": str(obligation.amount_due),
            "amount_paid": str(obligation.amount_paid),
            "remaining_balance": str(remaining_balance),
            "count": payments.count(),
            "total_amount": str(total_amount),
            "confirmed_amount": str(confirmed_amount),
            "refunded_amount": str(refunded_amount),
            "failed_count": payments.filter(status="failed").count(),
            "cancelled_count": payments.filter(status="cancelled").count(),
        }

        return Response(payload, status=status.HTTP_200_OK)
