from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.payments.models import Payment
from .serializers import PaymentSerializer


from django.db.models import Sum
from backend.contracts.models import Contract, ContractObligation

class PaymentListCreateAPIView(APIView):
    """
    GET  /api/payments/
    POST /api/payments/
    """

    def get(self, request):
        payments = Payment.objects.all().order_by("-created_at")
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
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

    def get_object(self, payment_id):
        try:
            return Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return None

    def get(self, request, payment_id):
        payment = self.get_object(payment_id)
        if payment is None:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, payment_id):
        payment = self.get_object(payment_id)
        if payment is None:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = PaymentSerializer(payment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, payment_id):
        payment = self.get_object(payment_id)
        if payment is None:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentConfirmAPIView(APIView):
    """
    POST /api/payments/<payment_id>/confirm/
    """

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.status = "confirmed"
        payment.confirmed_at = timezone.now()
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

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentFailAPIView(APIView):
    """
    POST /api/payments/<payment_id>/fail/
    """

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.status = "failed"
        payment.failed_at = timezone.now()
        payment.save(update_fields=["status", "failed_at", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentCancelAPIView(APIView):
    """
    POST /api/payments/<payment_id>/cancel/
    """

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.status = "cancelled"
        payment.cancelled_at = timezone.now()
        payment.save(update_fields=["status", "cancelled_at", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentRefundAPIView(APIView):
    """
    POST /api/payments/<payment_id>/refund/
    """

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.status = "refunded"
        payment.refunded_at = timezone.now()
        payment.save(update_fields=["status", "refunded_at", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)


class PaymentReverseAPIView(APIView):
    """
    POST /api/payments/<payment_id>/reverse/
    """

    def post(self, request, payment_id):
        try:
            payment = Payment.objects.get(id=payment_id)
        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.status = "reversed"
        payment.reversed_at = timezone.now()
        payment.save(update_fields=["status", "reversed_at", "updated_at"])

        return Response(PaymentSerializer(payment).data, status=status.HTTP_200_OK)

class ContractPaymentListCreateAPIView(APIView):
    """
    GET  /api/payments/contracts/<contract_id>/
    POST /api/payments/contracts/<contract_id>/
    """

    def get(self, request, contract_id):
        payments = Payment.objects.filter(contract_id=contract_id).order_by("-created_at")
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, contract_id):
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return Response(
                {"error": "Contract not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data.copy()
        data["contract"] = str(contract.id)

        serializer = PaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
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
        payments = Payment.objects.filter(payment_obligation_id=obligation_id).order_by("-created_at")
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, obligation_id):
        try:
            obligation = ContractObligation.objects.get(id=obligation_id)
        except ContractObligation.DoesNotExist:
            return Response(
                {"error": "Payment obligation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data.copy()
        data["contract"] = str(obligation.contract_id)
        data["payment_obligation"] = str(obligation.id)

        serializer = PaymentSerializer(data=data)
        serializer.is_valid(raise_exception=True)
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
        payments = Payment.objects.all()

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
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return Response(
                {"error": "Contract not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

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
        try:
            obligation = ContractObligation.objects.get(id=obligation_id)
        except ContractObligation.DoesNotExist:
            return Response(
                {"error": "Payment obligation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        payments = Payment.objects.filter(payment_obligation_id=obligation.id)

        total_amount = payments.aggregate(total=Sum("amount"))["total"] or 0
        confirmed_amount = payments.filter(status="confirmed").aggregate(total=Sum("amount"))["total"] or 0
        refunded_amount = payments.filter(status="refunded").aggregate(total=Sum("amount"))["total"] or 0

        payload = {
            "obligation_id": str(obligation.id),
            "contract_id": str(obligation.contract_id),
            "count": payments.count(),
            "total_amount": str(total_amount),
            "confirmed_amount": str(confirmed_amount),
            "refunded_amount": str(refunded_amount),
            "failed_count": payments.filter(status="failed").count(),
            "cancelled_count": payments.filter(status="cancelled").count(),
        }

        return Response(payload, status=status.HTTP_200_OK)





        