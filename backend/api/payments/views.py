
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.payments.models import Payment
from .serializers import PaymentSerializer


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